from app.tools.definitions import TOOL_MODELS, get_openai_tool_definitions


def test_openai_tool_definitions_use_standard_function_format() -> None:
    definitions = get_openai_tool_definitions()

    assert len(definitions) == len(TOOL_MODELS)
    for definition in definitions:
        assert definition["type"] == "function"
        assert definition["function"]["name"] in TOOL_MODELS
        assert definition["function"]["parameters"]["type"] == "object"
        assert "properties" in definition["function"]["parameters"]


def test_can_request_subset_of_tool_definitions() -> None:
    definitions = get_openai_tool_definitions(["generate_swot", "check_stage_readiness"])

    assert [item["function"]["name"] for item in definitions] == [
        "generate_swot",
        "check_stage_readiness",
    ]
