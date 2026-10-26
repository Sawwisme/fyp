USE veterinary_dental_care;
ALTER TABLE consultations
ADD COLUMN ai_analysis_id INT NULL,
    ADD CONSTRAINT fk_consultation_ai_analysis FOREIGN KEY (ai_analysis_id) REFERENCES ai_analysis_results(analysis_id);