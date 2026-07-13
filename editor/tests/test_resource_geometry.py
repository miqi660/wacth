from ultra3_editor.resource_geometry import MAIN_RESOURCE, THUMBNAIL_RESOURCE


def test_verified_resource_canvas_sizes() -> None:
    assert (MAIN_RESOURCE.width, MAIN_RESOURCE.height) == (320, 384)
    assert (THUMBNAIL_RESOURCE.width, THUMBNAIL_RESOURCE.height) == (210, 252)


def test_both_resource_canvases_use_five_to_six_ratio() -> None:
    assert MAIN_RESOURCE.aspect_ratio == (5, 6)
    assert THUMBNAIL_RESOURCE.aspect_ratio == (5, 6)
    assert MAIN_RESOURCE.width * 6 == MAIN_RESOURCE.height * 5
    assert THUMBNAIL_RESOURCE.width * 6 == THUMBNAIL_RESOURCE.height * 5


def test_main_and_thumbnail_are_independent_specs() -> None:
    assert MAIN_RESOURCE is not THUMBNAIL_RESOURCE
    assert MAIN_RESOURCE.name == "main"
    assert THUMBNAIL_RESOURCE.name == "thumbnail"
