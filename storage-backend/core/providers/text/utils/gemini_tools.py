"""Helper utilities for configuring Gemini tooling."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Mapping

from google.genai import types  # type: ignore

logger = logging.getLogger("core.providers.text.gemini")


def _parse_iso_datetime(value: Any) -> datetime | None:
    """Return a datetime parsed from ISO string values."""

    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return None
        if candidate.endswith("Z"):
            candidate = f"{candidate[:-1]}+00:00"
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:  # pragma: no cover - defensive logging
            logger.warning("Gemini could not parse ISO datetime: %s", value)
            return None

    return None


def _should_enable_tool(config: Any) -> bool:
    """Return True when the provided tool configuration should be enabled."""

    if isinstance(config, Mapping):
        if "enabled" in config:
            return bool(config.get("enabled"))
        return True

    if isinstance(config, (list, tuple, set)):
        return bool(config)

    return bool(config)


def build_gemini_tools(
    tool_settings: Mapping[str, Any] | None,
) -> tuple[list[types.Tool], dict[str, Any]]:
    """Translate BetterAI tool settings into Gemini tool definitions."""

    if not isinstance(tool_settings, Mapping) or not tool_settings:
        return [], {}

    tools: list[types.Tool] = []
    log_payload: dict[str, Any] = {}

    google_search_settings = tool_settings.get("google_search")
    if _should_enable_tool(google_search_settings):
        search_kwargs: dict[str, Any] = {}
        search_log: dict[str, Any] = {"enabled": True}

        if isinstance(google_search_settings, Mapping):
            exclude_domains = google_search_settings.get("exclude_domains")
            if isinstance(exclude_domains, (list, tuple, set)):
                cleaned_domains = [
                    str(domain).strip()
                    for domain in exclude_domains
                    if str(domain).strip()
                ]
                if cleaned_domains:
                    search_kwargs["exclude_domains"] = cleaned_domains
                    search_log["exclude_domains"] = cleaned_domains

            time_range = (
                google_search_settings.get("time_range")
                or google_search_settings.get("timeRange")
            )
            if isinstance(time_range, Mapping):
                start_value = (
                    time_range.get("start")
                    or time_range.get("start_time")
                    or time_range.get("startTime")
                )
                end_value = (
                    time_range.get("end")
                    or time_range.get("end_time")
                    or time_range.get("endTime")
                )
                start_dt = _parse_iso_datetime(start_value)
                end_dt = _parse_iso_datetime(end_value)
                if start_dt or end_dt:
                    search_kwargs["time_range_filter"] = types.Interval(
                        start_time=start_dt,
                        end_time=end_dt,
                    )
                    search_log["time_range"] = {
                        "start": start_dt.isoformat() if start_dt else None,
                        "end": end_dt.isoformat() if end_dt else None,
                    }

            dynamic_cfg = (
                google_search_settings.get("dynamic_retrieval")
                or google_search_settings.get("dynamicRetrieval")
            )
            if isinstance(dynamic_cfg, Mapping):
                dynamic_kwargs: dict[str, Any] = {}
                dynamic_log: dict[str, Any] = {}

                mode_value = dynamic_cfg.get("mode")
                if isinstance(mode_value, str):
                    normalised = mode_value.strip().upper()
                    try:
                        mode_enum = types.DynamicRetrievalConfigMode[normalised]
                        dynamic_kwargs["mode"] = mode_enum
                        dynamic_log["mode"] = mode_enum.name
                    except KeyError:  # pragma: no cover - defensive logging
                        logger.warning(
                            "Gemini received unknown dynamic retrieval mode: %s",
                            mode_value,
                        )

                threshold_value = (
                    dynamic_cfg.get("dynamic_threshold")
                    or dynamic_cfg.get("dynamicThreshold")
                )
                if isinstance(threshold_value, (int, float)):
                    dynamic_kwargs["dynamic_threshold"] = float(threshold_value)
                    dynamic_log["dynamic_threshold"] = float(threshold_value)

                if dynamic_kwargs:
                    tools.append(
                        types.Tool(
                            google_search_retrieval=types.GoogleSearchRetrieval(
                                dynamic_retrieval_config=types.DynamicRetrievalConfig(
                                    **dynamic_kwargs
                                )
                            )
                        )
                    )
                    if dynamic_log:
                        log_payload["google_search_retrieval"] = dynamic_log

        tools.append(
            types.Tool(google_search=types.GoogleSearch(**search_kwargs))
        )
        log_payload["google_search"] = search_log

    url_context_settings = tool_settings.get("url_context")
    if _should_enable_tool(url_context_settings):
        url_log: dict[str, Any] = {"enabled": True}
        urls: list[str] = []
        if isinstance(url_context_settings, Mapping):
            candidate_urls = (
                url_context_settings.get("urls")
                or url_context_settings.get("references")
                or url_context_settings.get("links")
            )
        elif isinstance(url_context_settings, (list, tuple, set)):
            candidate_urls = url_context_settings
        else:
            candidate_urls = None

        if isinstance(candidate_urls, (list, tuple, set)):
            urls = [
                str(item).strip()
                for item in candidate_urls
                if str(item).strip()
            ]
        if urls:
            url_log["urls"] = urls

        tools.append(types.Tool(url_context=types.UrlContext()))
        log_payload["url_context"] = url_log

    code_execution_settings = tool_settings.get("code_execution")
    if _should_enable_tool(code_execution_settings):
        tools.append(types.Tool(code_execution=types.ToolCodeExecution()))
        log_payload["code_execution"] = {"enabled": True}

    function_settings = tool_settings.get("functions")
    if isinstance(function_settings, (list, tuple)):
        declarations: list[types.FunctionDeclaration] = []
        for entry in function_settings:
            if not isinstance(entry, Mapping):
                continue
            name = entry.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            description = entry.get("description") or ""
            parameters = entry.get("parameters") or {"type": "object"}
            declarations.append(
                types.FunctionDeclaration(
                    name=name.strip(),
                    description=str(description or ""),
                    parametersJsonSchema=parameters,
                )
            )
        if declarations:
            tools.append(types.Tool(function_declarations=declarations))
            log_payload["functions"] = [decl.name for decl in declarations if decl.name]

    return tools, log_payload


__all__ = ["build_gemini_tools"]
