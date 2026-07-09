"""Official PSGC place names for Lanao del Sur.

Loaded once from static/data/lanao_del_sur.json (40 municipalities,
1,159 barangays). Used by the step-by-step address picker to make sure
only real provinces/municipalities/barangays can be saved — even if
someone bypasses the UI and posts the form directly.
"""
import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings

PROVINCE = 'Lanao del Sur'
# A list (not just the single constant above) so the picker and its
# validation can grow to cover more provinces later without changing
# their shape — right now there's only one valid entry.
PROVINCES = [PROVINCE]


@lru_cache(maxsize=1)
def municipalities():
    """{municipality: [barangay, ...]} for Lanao del Sur."""
    path = Path(settings.BASE_DIR) / 'static' / 'data' / 'lanao_del_sur.json'
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def is_valid_province(name):
    return name in PROVINCES


def is_valid_municipality(name):
    return name in municipalities()


def is_valid_barangay(municipality, barangay):
    return barangay in municipalities().get(municipality, [])


@lru_cache(maxsize=1)
def ph_provinces_cities():
    """{province: [city/municipality, ...]} for the ENTIRE Philippines —
    used only by the Place of Birth picker. Unlike the address picker
    (which is deliberately locked to the clinic's own service area,
    Lanao del Sur), a patient can have been born anywhere in the
    country, so this one isn't restricted to a single province.
    No barangay level here — a birthplace is recorded as just
    city/municipality + province, never down to the barangay/street.
    """
    path = Path(settings.BASE_DIR) / 'static' / 'data' / 'ph_provinces_cities.json'
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def is_valid_ph_province(name):
    return name in ph_provinces_cities()


def is_valid_ph_city(province, city):
    return city in ph_provinces_cities().get(province, [])


def validate_place_of_birth_data(data, required=False):
    """Shared clean() helper for the Place of Birth picker (nationwide
    province + city/municipality — no barangay/street needed).
    """
    prov = (data.get('pob_province') or '').strip()
    city = (data.get('pob_city') or '').strip()
    if not prov and not city:
        if required:
            return 'Please choose your place of birth (province and city/municipality).'
        return None
    if not is_valid_ph_province(prov):
        return 'Please choose a valid province.'
    if not is_valid_ph_city(prov, city):
        return 'Please choose a valid city/municipality for %s.' % prov
    return None


def validate_picker_data(data, forms, required=False):
    """Shared clean() helper for forms that use the address picker.

    `data` is the form's raw self.data; returns an error string or None.
    When required=False it only validates if the picker's companion
    fields were submitted, so legacy clients are unaffected. When
    required=True (account creation) a province, municipality, and
    barangay MUST all be chosen, in that order.
    """
    prov = (data.get('addr_province') or '').strip()
    mun = (data.get('addr_municipality') or '').strip()
    brgy = (data.get('addr_barangay') or '').strip()
    if not prov and not mun and not brgy:
        if required:
            return 'Please choose your province, municipality, and barangay.'
        return None
    if not is_valid_province(prov):
        return 'Please choose a valid province.'
    if not is_valid_municipality(mun):
        return 'Please choose a valid municipality in %s.' % prov
    if not is_valid_barangay(mun, brgy):
        return 'Please choose a valid barangay for %s.' % mun
    return None
