import asyncio
import logging

from sqlalchemy import select

from app.db.session import async_session_maker
from app.models.doctor import Specialization

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

INITIAL_SPECIALIZATIONS = [
    {"name": "General Medicine", "description": "Primary healthcare, chronic diseases, and general diagnosis."},
    {"name": "Cardiology", "description": "Heart and cardiovascular system disorders, hypertension, and arrhythmias."},
    {"name": "Pediatrics", "description": "Medical care of infants, children, and adolescents."},
    {"name": "Gynecology and Obstetrics", "description": "Women's reproductive health, pregnancy, and childbirth."},
    {"name": "Neurology", "description": "Nervous system disorders, stroke, epilepsy, and migraines."},
    {"name": "Orthopedics", "description": "Bone, joint, muscle, ligament, and tendon care and surgeries."},
    {"name": "Dermatology", "description": "Skin, hair, and nail disorders, cosmetic and medical dermatology."},
    {"name": "Gastroenterology", "description": "Digestive system, stomach, liver, and bowel diseases."},
    {"name": "Pulmonology / Respiratory Medicine", "description": "Lungs and respiratory tract diseases, asthma, COPD."},
    {"name": "Nephrology", "description": "Kidney care, renal failure, and dialysis management."},
    {"name": "Endocrinology", "description": "Hormone disorders, diabetes, thyroid disorders."},
    {"name": "ENT", "description": "Ear, nose, and throat conditions and head/neck surgery."},
    {"name": "Ophthalmology", "description": "Eye care, vision problems, and ocular surgery."},
    {"name": "Psychiatry", "description": "Mental health diagnosis, treatment, and counseling."},
    {"name": "Emergency Medicine / ER", "description": "Immediate critical care for acute life-threatening conditions."},
]


async def seed_specializations():
    async with async_session_maker() as db:
        logger.info("Checking existing specializations...")
        for spec_data in INITIAL_SPECIALIZATIONS:
            result = await db.execute(
                select(Specialization).where(Specialization.name == spec_data["name"])
            )
            existing = result.scalar_one_or_none()
            if not existing:
                spec = Specialization(
                    name=spec_data["name"],
                    description=spec_data["description"],
                    is_active=True,
                )
                db.add(spec)
                logger.info(f"Adding specialization: {spec_data['name']}")
        await db.commit()
        logger.info("Seed completed successfully.")


if __name__ == "__main__":
    asyncio.run(seed_specializations())
