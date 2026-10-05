"""Hospital department aliases mapped to Spandan's specialist categories."""

ALIASES = {
    "General Medicine": ("Internal Medicine",),
    "Cardiology": ("Cardiology Care Centre",),
    "Pediatrics": ("Paediatrics",),
    "Gynecology and Obstetrics": ("Obstetrics and Gynaecology",),
    "Orthopedics": ("Orthopaedics",),
    "Dermatology": ("Dermatology & Venereology",),
    "Gastroenterology": ("Gastroenterology & Hepatology",),
    "Pulmonology / Respiratory Medicine": ("Respiratory Medicine",),
    "Endocrinology": ("Diabetology & Endocrinology",),
    "ENT": ("ENT & Head Neck Surgery",),
    "Emergency Medicine / ER": ("Accident & Emergency",),
    "General Surgery": ("General & Laparoscopic Surgery",),
}
BENGALI = {
    "হৃদরোগ": "Cardiology",
    "শিশু": "Pediatrics",
    "চর্ম": "Dermatology",
    "চোখ": "Ophthalmology",
    "মানসিক": "Psychiatry",
    "কিডনি": "Nephrology",
    "ডায়াবেটিস": "Endocrinology",
    "নাক কান গলা": "ENT",
    "হাড়": "Orthopedics",
    "স্ত্রীরোগ": "Gynecology and Obstetrics",
    "স্নায়ু": "Neurology",
}


def canonical_specialty(value):
    value = BENGALI.get(value.strip(), value.strip())
    for name, aliases in ALIASES.items():
        if value.lower() in {name.lower(), *(alias.lower() for alias in aliases)}:
            return name
    return value


def department_names(value):
    canonical = canonical_specialty(value)
    return [canonical.lower(), *(alias.lower() for alias in ALIASES.get(canonical, ()))]
