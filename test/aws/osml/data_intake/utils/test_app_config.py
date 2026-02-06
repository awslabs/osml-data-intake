#  Copyright 2024-2026 Amazon.com, Inc. or its affiliates.

from aws.osml.data_intake.utils.app_config import get_minimal_collection_dict


class TestAppConfig:
    def test_minimal_collection(self):
        mock_collection_id = "test-collection"
        expected_minimal_collection = {
            "type": "Collection",
            "stac_version": "1.0.0",
            "id": mock_collection_id,
            "description": f"{mock_collection_id} STAC Collection",
            "license": "",
            "extent": {"spatial": {"bbox": [[-180.0, -90.0, 180.0, 90.0]]}, "temporal": {"interval": []}},
            "links": [{"href": "", "rel": "self"}],
        }

        collection_dict = get_minimal_collection_dict(mock_collection_id)

        assert collection_dict == expected_minimal_collection
