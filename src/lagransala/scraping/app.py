from pathlib import Path

import yaml

from lagransala.scraping.models import VenueSpec


def venue_specs_from_yaml(path: Path):
    with open(path) as f:
        raw_specs = yaml.safe_load(f)
        return [VenueSpec.model_validate(raw_spec) for raw_spec in raw_specs]
