"""Read-only operational reports. Collections use the completed transaction ledger."""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select, func, case, or_
from app.models import (Appointment, Schedule, TimeSlot, Veterinarian, Consultation,
    Treatment, TreatmentProgress, Prescription, FollowupCare, Order, Payment,
    Transaction, ConsultationBill)
from app.services.admin_profile_service import get_admin_record
from app.services.vet_profile_service import get_profile

MYT = ZoneInfo('Asia/Kuala_Lumpur')


def period(start, end):
    today = datetime.now(MYT).date()
    start = start or today.replace(day=1)
    end = end or today
    if end < start or (end-start).days > 365:
        raise HTTPException(422, 'Choose a valid date range of at most 366 days.')
    if start < date(1900, 1, 1) or end == date.max:
        raise HTTPException(422, 'Dates are outside the supported range.')
    def utc(value):
        return datetime.combine(value, time.min, MYT).astimezone(timezone.utc).replace(tzinfo=None)
    return start, end, utc(start), utc(end+timedelta(days=1))


def appointment_scope(clinic_id, vet_id=None):
    statement = (select(Appointment).join(TimeSlot).join(Schedule)
        .join(Veterinarian, Veterinarian.veterinarian_id == Schedule.veterinarian_id)
        .where(Veterinarian.clinic_id == clinic_id))
    if vet_id is not None:
        statement = statement.where(Appointment.veterinarian_id == vet_id,
                                    Schedule.veterinarian_id == vet_id)
    return statement


def count_rows(db, statement):
    return db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0


def status_counts(db, statement, column):
    sub = statement.with_only_columns(column.label('status')).order_by(None).subquery()
    return [dict(status=status or 'unknown', count=count) for status,count in
            db.execute(select(sub.c.status,func.count()).group_by(sub.c.status).order_by(sub.c.status))]


def local_day(db, column):
    if db.get_bind().dialect.name == 'sqlite':
        return func.date(column, '+8 hours')
    # Numeric offsets do not require MySQL time-zone tables.
    return func.date(func.convert_tz(column, '+00:00', '+08:00'))


def build_report(db, user, start=None, end=None):
    start,end,utc_start,utc_end = period(start,end)
    admin = user.role == 'clinic_administrator'
    profile = get_admin_record(db,user) if admin else get_profile(db,user)
    clinic_id = profile.clinic_id
    vet_id = None if admin else profile.veterinarian_id
    appts = appointment_scope(clinic_id,vet_id).where(
        Appointment.appointment_date >= start, Appointment.appointment_date <= end)
    consults = select(Consultation).where(Consultation.clinic_id == clinic_id,
        Consultation.consultation_date >= utc_start, Consultation.consultation_date < utc_end)
    if vet_id is not None:
        consults = consults.where(Consultation.veterinarian_id == vet_id)
    # Treatment and prescription dates are their recorded clinical dates.
    clinical_scope = select(Consultation.consultation_id).where(
        Consultation.clinic_id == clinic_id, Consultation.status == 'completed')
    if vet_id is not None:
        clinical_scope = clinical_scope.where(Consultation.veterinarian_id == vet_id)
    treatments = (select(Treatment).outerjoin(TreatmentProgress)
        .where(Treatment.consultation_id.in_(clinical_scope),
               Treatment.treatment_date >= start,Treatment.treatment_date <= end))
    prescriptions = select(Prescription).where(Prescription.consultation_id.in_(clinical_scope),
        Prescription.prescription_date >= start,Prescription.prescription_date <= end)
    followups = select(FollowupCare).where(FollowupCare.consultation_id.in_(clinical_scope),
        FollowupCare.recommended_date >= start,FollowupCare.recommended_date <= end)
    if vet_id is not None:
        followups=followups.where(FollowupCare.veterinarian_id == vet_id)
    patient_ids = appts.with_only_columns(Appointment.pet_id).union(
        consults.with_only_columns(Consultation.pet_id)).subquery()
    appointment_statuses=status_counts(db,appts,Appointment.status)
    consultation_statuses=status_counts(db,consults,Consultation.status)
    treatment_statuses=status_counts(db,treatments,func.coalesce(TreatmentProgress.status,Treatment.status))
    followup_statuses=status_counts(db,followups,FollowupCare.status)
    result=dict(role='admin' if admin else 'vet',date_from=start,date_to=end,
        summary=dict(appointments=count_rows(db,appts),
            completed_consultations=sum(x['count'] for x in consultation_statuses if x['status']=='completed'),
            patients=db.scalar(select(func.count()).select_from(patient_ids)) or 0,
            treatments=count_rows(db,treatments),prescriptions=count_rows(db,prescriptions),
            followups_due=count_rows(db,followups)),
        appointment_statuses=appointment_statuses,consultation_statuses=consultation_statuses,
        treatment_statuses=treatment_statuses,followup_statuses=followup_statuses)
    grouped=db.execute(select(local_day(db,Consultation.consultation_date),func.count())
        .where(Consultation.consultation_id.in_(consults.with_only_columns(Consultation.consultation_id)),
               Consultation.status=='completed')
        .group_by(local_day(db,Consultation.consultation_date))).all()
    consult_days={str(day):count for day,count in grouped}
    result['daily']=[dict(date=(start+timedelta(days=i)).isoformat(),
        consultations=consult_days.get((start+timedelta(days=i)).isoformat(),0))
        for i in range((end-start).days+1)]
    if admin:
        result['financial']=financial_report(db,clinic_id,utc_start,utc_end)
        orders=select(Order).where(Order.clinic_id==clinic_id,Order.order_date>=utc_start,Order.order_date<utc_end)
        result['summary']['orders']=count_rows(db,orders)
        result['order_statuses']=status_counts(db,orders,Order.order_status)
    return result


def financial_report(db, clinic_id, start, end):
    clinic_orders=select(Order.order_id).where(Order.clinic_id==clinic_id)
    clinic_bills=select(ConsultationBill.consultation_bill_id).where(ConsultationBill.clinic_id==clinic_id)
    clinic_appointments=appointment_scope(clinic_id).with_only_columns(Appointment.appointment_id)
    scope=or_(Payment.order_id.in_(clinic_orders),
              Payment.consultation_bill_id.in_(clinic_bills),
              (Payment.payment_purpose=='booking_deposit') & Payment.appointment_id.in_(clinic_appointments))
    source=case((Payment.order_id.is_not(None),'shop'),
                (Payment.consultation_bill_id.is_not(None),'consultation_balance'),else_='booking_deposit')
    statement=(select(source.label('source'),Payment.payment_method,Transaction.transaction_type,
                      func.sum(Transaction.amount))
        .select_from(Transaction).join(Payment,Payment.payment_id==Transaction.payment_id)
        .where(scope,Transaction.transaction_status=='completed',
            Transaction.transaction_type.in_(['payment','refund']),
            Transaction.transaction_date>=start,Transaction.transaction_date<end)
        .group_by(source,Payment.payment_method,Transaction.transaction_type))
    collected=Decimal('0'); refunded=Decimal('0'); buckets={}
    for channel,method,kind,amount in db.execute(statement):
        key=(channel,method)
        bucket=buckets.setdefault(key,dict(source=channel,method=method,collected=Decimal('0'),refunded=Decimal('0')))
        if kind=='payment': collected+=amount;bucket['collected']+=amount
        else: refunded+=amount;bucket['refunded']+=amount
    rows=[dict(source=b['source'],method=b['method'],collected=str(b['collected']),
        refunded=str(b['refunded']),net=str(b['collected']-b['refunded'])) for _,b in sorted(buckets.items())]
    return dict(collected=str(collected),refunded=str(refunded),net=str(collected-refunded),breakdown=rows)
