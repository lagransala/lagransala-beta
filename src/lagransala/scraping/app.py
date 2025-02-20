import yaml

from lagransala.scraping.models import VenueExtractionDef


def venue_extraction_defs_from_yaml():
    raw_specs = yaml.safe_load(open("./seeders/specs.yaml"))
    return [VenueExtractionDef.model_validate(raw_spec) for raw_spec in raw_specs]
