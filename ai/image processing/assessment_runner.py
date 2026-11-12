"""Headless entry point for the existing dental models; no web/database imports.

Use --check to inspect local dependencies and model files without loading models.
Analysis writes into a caller-selected private output directory. The web API will
be responsible for authenticating users and serving authorised output files.
"""
import argparse
from contextlib import redirect_stdout
import importlib.util
import json
from pathlib import Path
import shutil
import sys
from uuid import uuid4

MODEL_FILES = (
    "dental_image_validator.keras",
    "dental_classifier.keras",
    "dental_segmentation_mobilenet_unet.keras",
)

DEPENDENCIES = ('tensorflow', 'cv2', 'numpy', 'matplotlib')
BASE_DIR = Path(__file__).resolve().parent


def check_setup():
    missing_packages = [name for name in DEPENDENCIES if importlib.util.find_spec(name) is None]
    missing_models = [name for name in MODEL_FILES if not (BASE_DIR/'models'/name).is_file()]
    return dict(status='ready' if not missing_packages and not missing_models else 'not_ready',
                missing_packages=missing_packages, missing_models=missing_models,
                models_loaded=False)


def json_value(value):
    if hasattr(value, 'tolist'):
        return value.tolist()
    if hasattr(value, 'item'):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f'Unsupported result type: {type(value).__name__}')


def run(image_path, output_dir):
    source = Path(image_path).resolve(strict=True)
    if not source.is_file() or source.suffix.lower() not in {'.jpg', '.jpeg', '.png'}:
        raise ValueError('Choose a JPG or PNG image file.')
    if source.stat().st_size > 10 * 1024 * 1024:
        raise ValueError('The image must not exceed 10 MB.')
    setup = check_setup()
    if setup['status'] != 'ready':
        return setup
    # A new private folder and filename prevent uploads with identical names
    # from overwriting each other's images and analysis artefacts.
    request_id = uuid4().hex
    output = Path(output_dir).resolve()/request_id
    output.mkdir(parents=True, exist_ok=False)
    input_path = output/('input'+source.suffix.lower())
    shutil.copy2(source, input_path)
    with redirect_stdout(sys.stderr):
        import matplotlib
        matplotlib.use('Agg', force=True)
        import matplotlib.pyplot as plt
        # The existing research scripts call show(); the runner must be headless.
        plt.show = lambda *args, **kwargs: None
        import gradcam
        import segmentation_inference
        import dental_analysis
        # The research script treats the validator as optional. Application
        # inference must not silently bypass that validation gate.
        if gradcam.dental_validator_model is None:
            raise RuntimeError('The dental-image validator could not be loaded.')
        gradcam.OUTPUT_DIR = str(output/'gradcam')
        segmentation_inference.OUTPUT_DIR = str(output/'segmentation')
        Path(gradcam.OUTPUT_DIR).mkdir()
        Path(segmentation_inference.OUTPUT_DIR).mkdir()
        rejection_message = None

        try:
            result = dental_analysis.analyze_dental_image(
                str(input_path),
                output_dir=str(output),
                raise_on_rejection=True,
            )

        except gradcam.ImageValidationError as error:
            result = None

            if error.stage == "quality":
                # Existing messages explain blur, lighting or resolution.
                rejection_message = str(error)

            elif error.stage == "content":
                rejection_message = (
                    "A suitable cat or dog dental region was not detected. "
                    "Take a clear close-up of your pet's teeth and gums."
                )

            else:
                rejection_message = (
                    "The photo could not be processed. "
                    "Choose a readable JPG or PNG image."
                )

        finally:
            plt.close("all")

    if result is None:
        response = {
            "status": "rejected",
            "request_id": request_id,
            "message": rejection_message or (
                "The photo did not pass validation. "
                "Take a clear close-up of your pet's teeth and gums."
            ),
        }
    else:
        response = dict(status='completed', request_id=request_id,
            severity_method='experimental_rule_based',
            interpretation='Model output for veterinary review; this is not a confirmed diagnosis.',
            result=result)
    # allow_nan=False prevents invalid JSON from silently carrying NaN scores.
    encoded = json.dumps(response, default=json_value, allow_nan=False, ensure_ascii=False)
    (output/'result.json').write_text(encoded, encoding='utf-8')
    return json.loads(encoded)


def serve():
    # Serial requests reuse the models imported by run(). Logs stay on stderr.
    for line in sys.stdin:
        request_id = None
        try:
            request = json.loads(line)
            request_id = request["id"]
            with redirect_stdout(sys.stderr):
                response = run(request["image"], request["output_dir"])
        except Exception as error:
            print(f"Assessment runner: {type(error).__name__}: {error}",
                  file=sys.stderr, flush=True)
            response = {"status": "failed"}
        print(json.dumps({"id": request_id, "response": response},
                         default=json_value, allow_nan=False), flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--serve', action='store_true')
    parser.add_argument('--image')
    parser.add_argument('--output-dir')
    args = parser.parse_args()
    if args.serve:
        return serve()
    if not args.check and (not args.image or not args.output_dir):
        parser.error('Provide --image and --output-dir, or use --check.')
    try:
        result = check_setup() if args.check else run(args.image, args.output_dir)
        print(json.dumps(result, default=json_value, allow_nan=False, ensure_ascii=False))
        return 0 if result['status'] in {'ready','completed','rejected'} else 2
    except Exception as error:
        print(f'Assessment runner: {type(error).__name__}: {error}', file=sys.stderr)
        print(json.dumps(dict(status='failed', message='The assessment could not be completed. Check the local inference log.')))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
