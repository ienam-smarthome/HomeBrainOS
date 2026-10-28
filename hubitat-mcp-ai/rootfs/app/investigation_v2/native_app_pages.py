"""Bounded read-only metadata for Hubitat app-page navigation.

Configuration page titles and page counts are non-execution evidence. Never
project arbitrary form values, page HTML, links, script, settings or notes.
"""
from __future__ import annotations
from typing import Any
from .native_source_adapters import safe_string, unwrapped
from .native_provenance import numeric_id


def app_pages_summary(data: Any) -> dict[str,Any]:
    raw=unwrapped(data)
    result={"source_complete":False,
            "app_pages_projection_basis":"navigation metadata only",
            "settings_values_projected":False,
            "app_page_code_inspected":False}
    if type(raw.get("success")) is bool:
        result["success"]=raw["success"]
    app=raw.get("app")
    if isinstance(app,dict):
        app_id=numeric_id(app.get("appId") or app.get("id"))
        if app_id:
            result["returned_app_id"]=app_id
        for name in ("name","label"):
            if isinstance(app.get(name),str):
                result["app_"+name]=safe_string(app[name],95)
    primary=raw.get("primaryPage")
    if isinstance(primary,str):
        result["primary_page"]=safe_string(primary,70)
    elif isinstance(primary,dict):
        name=primary.get("name") or primary.get("pageName")
        if isinstance(name,str):
            result["primary_page"]=safe_string(name,70)
    pages=raw.get("pages")
    if isinstance(pages,list):
        result["reported_page_count"]=len(pages)
        names=[]
        for item in pages[:40]:
            name=item if isinstance(item,str) else (
                item.get("name") or item.get("pageName")
                if isinstance(item,dict) else None)
            if isinstance(name,str) and name:
                names.append(safe_string(name,75))
        result["page_names"]=names[:24]
        result["page_names_partial"] = (
            len(pages)>40 or len(names)<len(pages))
    result["navigation_only"]=True
    return result


__all__=["app_pages_summary"]
