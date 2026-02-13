from core.pydantic_schemas import ApiResponse, api_response, error, ok


def test_ok_helper_returns_success_envelope():
    result = ok("Garmin data stored", data={"rows": 3})

    assert result == {
        "code": 200,
        "success": True,
        "message": "Garmin data stored",
        "data": {"rows": 3},
        "meta": None,
    }


def test_error_helper_requires_error_code():
    result = error(404, "Garmin record not found")

    assert result["code"] == 404
    assert result["success"] is False
    assert result["message"] == "Garmin record not found"


def test_error_helper_rejects_success_code():
    try:
        error(200, "should fail")
    except ValueError as exc:
        assert "Error responses must" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("error helper accepted success code")


def test_api_response_model_dump_matches_payload():
    envelope = ApiResponse[int](code=201, success=True, message="created", data=1)

    assert envelope.model_dump() == {
        "code": 201,
        "success": True,
        "message": "created",
        "data": 1,
        "meta": None,
    }


def test_api_response_supports_meta_payload():
    result = api_response(code=202, message="accepted", data=None, meta={"request_id": "abc"})

    assert result == {
        "code": 202,
        "success": True,
        "message": "accepted",
        "data": None,
        "meta": {"request_id": "abc"},
    }


def test_api_response_allows_structured_message():
    payload = {"status": "completed", "result": "https://example"}
    result = api_response(code=200, message=payload, data=None)

    assert result["message"] == payload
