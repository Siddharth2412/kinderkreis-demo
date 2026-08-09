from app.models import CareType, Provider

SEED_PROVIDERS: list[Provider] = [
    Provider(
        id=1,
        name="Anke Möller",
        city="Göttingen",
        min_age_months=0,
        max_age_months=36,
        care_type=CareType.individual,
        staff_count=1,
        capacity_total=5,
        capacity_used=3,
        qualification_hours=300,
        practicum_hours=80,
        has_pflegeerlaubnis=True,
        bio="Betreue seit 6 Jahren in meinem Zuhause im Grüner Weg, ruhige Umgebung mit Garten.",
    ),
    Provider(
        id=2,
        name='Großtagespflege "Sonnenkinder"',
        city="Hannover",
        min_age_months=12,
        max_age_months=72,
        care_type=CareType.group,
        staff_count=3,
        capacity_total=10,
        capacity_used=7,
        qualification_hours=340,
        practicum_hours=80,
        has_pflegeerlaubnis=True,
        bio="Drei Fachkräfte in gemeinsamen, kindgerechten Räumen nahe der Innenstadt.",
    ),
    Provider(
        id=3,
        name="Jonas Reinhardt",
        city="Braunschweig",
        min_age_months=24,
        max_age_months=60,
        care_type=CareType.individual,
        staff_count=1,
        capacity_total=5,
        capacity_used=1,
        qualification_hours=300,
        practicum_hours=80,
        has_pflegeerlaubnis=True,
        bio="Schwerpunkt auf Sprachförderung und Bewegung, kleine Gruppe mit viel Aufmerksamkeit.",
    ),
    Provider(
        id=4,
        name="Familientagespflege Nordstadt",
        city="Hannover",
        min_age_months=6,
        max_age_months=48,
        care_type=CareType.group,
        staff_count=2,
        capacity_total=8,
        capacity_used=8,
        qualification_hours=310,
        practicum_hours=80,
        has_pflegeerlaubnis=True,
        bio="Zwei erfahrene Tagespflegepersonen, aktuell voll belegt, Warteliste möglich.",
    ),
    Provider(
        id=5,
        name="Lina Bartels",
        city="Göttingen",
        min_age_months=0,
        max_age_months=24,
        care_type=CareType.individual,
        staff_count=1,
        capacity_total=4,
        capacity_used=0,
        qualification_hours=160,
        practicum_hours=40,
        has_pflegeerlaubnis=False,
        bio="Aktuell in der tätigkeitsbegleitenden Qualifizierung, Pflegeerlaubnis beantragt.",
    ),
]

_next_id = max(p.id for p in SEED_PROVIDERS) + 1


def get_next_id() -> int:
    global _next_id
    value = _next_id
    _next_id += 1
    return value
