                try:
                    semantic = await semantic_plan(
                    payload.question, audit_devices, agent.transport.chat,
                    timeout_seconds=25,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                cause=("timeout" if isinstance(exc,TimeoutError)
                       else "invalid_plan" if isinstance(exc,(ValueError,TypeError,KeyError))
                       else "provider_failure")
                logger.warning("V2 semantic plan unavailable: %s (%s)",
                               cause,type(exc).__name__)
                # If the real user named EXACTLY one inventory-verified
                # device, AI intent classification is not an authorisation
                # dependency for bounded read-only evidence collection.
                # No guessed ID, keyword router, or model-selected target.
                try:
                    fallback_ids, _, _ = resolve_verified_device_subjects(
                        payload.question, audit_devices)
                except ValueError:
                    fallback_ids = ()
                if len(fallback_ids) == 1:
                    semantic_failure = cause
                    logger.info("V2 single-device read-only fallback: %s", cause)
                else:
                    message=(
                        "HomeBrain retrieved Hubitat inventory, but could not "
                        "safely interpret the question. No device commands were "
                        "sent. Check the planning diagnostics in the report."
                    )
                    return {
                        "answer_mode":"semantic_unavailable",
                        "answer":{"text":message,"displayed_record_ids":[],
                                  "omitted_material_record_ids":[],
                                  "validation_issues":["semantic_plan_"+cause],
                                  "root_cause_verified":False,"human_review_required":True},
                        "report":{"text":message,"technical_answer_retained":False},
                        "semantic_diagnostics":{
                            "phase":"intent_planning","outcome":cause,
                            "inventory_ms":inventory_ms,
                            "planning_ms":round((time.perf_counter()-planning_started)*1000),
                            "inventory_devices":len(audit_devices),
                            "inventory_complete":inventory_provenance.get("complete") is True,
                        },
                        "resolved_devices":[],"resolution_method":"semantic_objective",
                        "elapsed_ms":round((time.perf_counter()-started)*1000),
                        "test_mode":"explicit_read_only",
                    }
            planning_ms=round((time.perf_counter()-planning_started)*1000)
            if semantic is not None and semantic.mode == "inventory":
                enrichment_started=time.perf_counter()
                semantic, role_diagnostic=await enrich_measurement_roles(
                    semantic, audit_devices, agent.transport.chat,
                    timeout_seconds=12,
                )
                try:
                    result = execute_inventory_plan(
                        semantic, audit_devices, inventory_provenance,
                        operator_roles=load_operator_meter_roles(
                            OPTIONS.get("v2_measurement_roles_json", "{}"),
                            audit_devices,
                        ),
                    )
                except ValueError as exc:
                    raise HTTPException(status_code=422,detail=str(exc)) from None
                result["elapsed_ms"]=round((time.perf_counter()-started)*1000)
                result["semantic_diagnostics"]={
                    "phase":"completed","outcome":"success",
                    "inventory_ms":inventory_ms,"planning_ms":planning_ms,
                    "role_enrichment_ms":round((time.perf_counter()-enrichment_started)*1000),
                    "meter_roles":role_diagnostic,
                    "inventory_devices":len(audit_devices),
                    "inventory_complete":inventory_provenance.get("complete") is True,
                }
                if role_diagnostic.get("outcome")=="unavailable":
                    result["answer"]["validation_issues"].append(
                        "optional_measurement_role_enrichment_unavailable"
                    )
                return result
            if semantic is not None and semantic.mode in ("unsupported","historical"):
                # Unsupported whole-house history must not be misrepresented
                # as a present-state inventory query or fabricated timeline.
                subject=("A cross-device historical comparison" if
                         semantic.mode=="historical" else "This question")
                message=(subject+" is not yet supported by the safe V2 "
                         "inventory executor. Current inventory answers and "
                         "single-device investigation are available; no "
                         "device state was changed.")
                return {
                    "answer_mode":"semantic_unavailable",
                    "answer":{"text":message,"displayed_record_ids":[],
                              "omitted_material_record_ids":[],
                              "validation_issues":["unsupported_evidence_objective"],
                              "root_cause_verified":False,"human_review_required":True},
                    "report":{"text":message,"technical_answer_retained":False},
                    "semantic_plan":semantic.to_dict(),
                    "resolved_devices":[],"resolution_method":"semantic_objective",
                    "elapsed_ms":round((time.perf_counter()-started)*1000),
                    "test_mode":"explicit_read_only",
                }
        try:
            # Named historical cases retain the existing strict read plan.
            # Device identities may come from the *model's phrase*, but only
            # live Hubitat names/IDs can satisfy the host verification gate.
            devices = (audit_devices if audit_devices is not None
                       else await mcp.get_cached_devices(refresh=True))
            if payload.device_ids or payload.device_name:
                # Explicit operator overrides keep their strict verification.
                ids, resolved, resolve_method = resolve_verified_device_subjects(
                    payload.question, devices, device_name=payload.device_name,
                    device_ids=payload.device_ids)
            else:
                # An AI name proposal must not override a clear name in the
                # question. Live Hubitat identity remains authoritative.
                ids, resolved, resolve_method = resolve_planned_device_subjects(
                    payload.question, devices,
                    model_device_name=(semantic.device_name if semantic is not None
                                       and semantic.scope=="named" else None))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        except Exception:
            raise HTTPException(status_code=503, detail="Hubitat identity verification unavailable") from None
        # Hub time is obtained from existing authoritative resolver. If
        # unavailable, do not silently invent a calendar: use UTC and show
        # the fallback basis in the explicit window metadata.
        zone_name = "UTC"
        if re.search(r"\d{1,2}\s*(?:-|–|—|to)\s*\d{1,2}\s+[A-Za-z]+\s+\d{4}|\b(?:today|yesterday)\b",
                     payload.question, re.I):
            try:
                _now_local, resolved_zone, _zone_basis = await _health_timezone.now_in_hub_timezone(
                    lambda: datetime.now(timezone.utc))
                if resolved_zone:
                    zone_name = resolved_zone
            except Exception:
                pass
        incident_window = explicit_incident_window(
            payload.question, zone_name=zone_name,
            now=datetime.now(timezone.utc),
        )
        try:
            evaluated = await evaluate_v2_with_model(
                explicitly_authorised=True,
                question=payload.question,
                chat=agent.transport.chat,
                mcp=mcp, executor=agent.executor,
                verified_entity_ids=ids,
                enable_atomic_claim_validation=True,
                enable_evidence_narrative=True,
                bootstrap_device_context=True,
                semantic_unavailable_reason=semantic_failure,
                max_rounds=3, max_total_reads=8,
                incident_window=incident_window,
                verified_device_label=resolved[0]["label"] if len(resolved)==1 else None,
                force_duration_mode=semantic is not None and semantic.mode=="duration",
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Opt-in V2 evaluation unavailable")
            raise HTTPException(status_code=503, detail="V2 evaluation failed; no Hubitat writes attempted") from None
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        result = evaluated.to_dict()
        result["elapsed_ms"] = elapsed_ms
        result["test_mode"] = "explicit_read_only"
        result["resolved_devices"] = resolved
        result["resolution_method"] = resolve_method
        if direct_verified_target is not None:
            result["answer_mode"] = "verified_device_investigation"
            result["semantic_diagnostics"] = {
                "phase": "evidence_first_verified_device",
                "outcome": "direct_verified_target",
                "inventory_ms": inventory_ms,
                "planning_ms": 0,
                "inventory_devices": len(audit_devices),
                "inventory_complete": inventory_provenance.get("complete") is True,
                "target_verified": True,
                "target_id": direct_verified_target,
                "model_intent_planning_skipped": True,
                "model_investigation_attempted": True,
            }
        if semantic_failure is not None:
            result["answer_mode"] = "semantic_fallback_investigation"
            result["semantic_diagnostics"] = {
                "phase": "host_only_evidence_recovery",
                "outcome": "partial_evidence_recovered",
                "reason": semantic_failure,
                "inventory_ms": inventory_ms,
                "planning_ms": planning_ms,
                "inventory_devices": len(audit_devices),
                "inventory_complete": inventory_provenance.get("complete") is True,
                "target_verified": True,
                "model_investigation_attempted": False,
            }
        if semantic is not None:
            result["semantic_plan"] = semantic.to_dict()
            result["answer_mode"] = ("semantic_duration" if semantic.mode=="duration"
                                    else "semantic_investigation")
        result["scorecard"] = replay_scorecard(
            evaluated.investigation.case, evaluated.answer,
            existing_v1_answer=payload.existing_v1_answer,
            reference_answer=payload.reference_answer,
            reads_executed=evaluated.investigation.executed_reads,
            elapsed_ms=elapsed_ms,
        )
        return result

    # Separate coordinator key: never cancel or reuse a production chat.
    return await request_coordinator.run(
        "investigation-v2-test-exclusive", experiment(),
        connection=connection, request_id=uuid.uuid4().hex,
        deadline_seconds=240,
    )


@app.post("/api/chat")
async def chat(request: ChatRequest, connection: Request) -> dict[str, Any]:
    return {"response": await _answer(request, connection)}


@app.post("/api/ask")
async def ask(request: ChatRequest, connection: Request) -> dict[str, Any]:
    started = time.perf_counter()
    outcome = await _answer_result(request, connection)
    result = build_agent_response(
        outcome,
        model=agent.model_name,
        elapsed_ms=round((time.perf_counter() - started) * 1000),
        version=VERSION,
    )
    result["model_tier_requested"] = request.model_tier
    return result


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8788, log_level="info", proxy_headers=True)
                try:
                    semantic = await semantic_plan(
                    payload.question, audit_devices, agent.transport.chat,
                    timeout_seconds=25,
                )
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    cause=("timeout" if isinstance(exc,TimeoutError)
                           else "invalid_plan" if isinstance(exc,(ValueError,TypeError,KeyError))
                           else "provider_failure")
                    logger.warning("V2 semantic plan unavailable: %s (%s)",
                                   cause,type(exc).__name__)
                    # If the real user named EXACTLY one inventory-verified
                    # device, AI intent classification is not an authorisation
                    # dependency for bounded read-only evidence collection.
                    # No guessed ID, keyword router, or model-selected target.
                    try:
                        fallback_ids, _, _ = resolve_verified_device_subjects(
                            payload.question, audit_devices)
                    except ValueError:
                        fallback_ids = ()
                    if len(fallback_ids) == 1:
                        semantic_failure = cause
                        logger.info("V2 single-device read-only fallback: %s", cause)
                    else:
                        message=(
                            "HomeBrain retrieved Hubitat inventory, but could not "
                            "safely interpret the question. No device commands were "
                            "sent. Check the planning diagnostics in the report."
                        )
                        return {
                            "answer_mode":"semantic_unavailable",
                            "answer":{"text":message,"displayed_record_ids":[],
                                      "omitted_material_record_ids":[],
                                      "validation_issues":["semantic_plan_"+cause],
                                      "root_cause_verified":False,"human_review_required":True},
                            "report":{"text":message,"technical_answer_retained":False},
                            "semantic_diagnostics":{
                                "phase":"intent_planning","outcome":cause,
                                "inventory_ms":inventory_ms,
                                "planning_ms":round((time.perf_counter()-planning_started)*1000),
                                "inventory_devices":len(audit_devices),
                                "inventory_complete":inventory_provenance.get("complete") is True,
                            },
                            "resolved_devices":[],"resolution_method":"semantic_objective",
                            "elapsed_ms":round((time.perf_counter()-started)*1000),
                            "test_mode":"explicit_read_only",
                        }
                planning_ms=round((time.perf_counter()-planning_started)*1000)
            if semantic is not None and semantic.mode == "inventory":
                enrichment_started=time.perf_counter()
                semantic, role_diagnostic=await enrich_measurement_roles(
                    semantic, audit_devices, agent.transport.chat,
                    timeout_seconds=12,
                )
                try:
                    result = execute_inventory_plan(
                        semantic, audit_devices, inventory_provenance,
                        operator_roles=load_operator_meter_roles(
                            OPTIONS.get("v2_measurement_roles_json", "{}"),
                            audit_devices,
                        ),
                    )
                except ValueError as exc:
                    raise HTTPException(status_code=422,detail=str(exc)) from None
                result["elapsed_ms"]=round((time.perf_counter()-started)*1000)
                result["semantic_diagnostics"]={
                    "phase":"completed","outcome":"success",
                    "inventory_ms":inventory_ms,"planning_ms":planning_ms,
                    "role_enrichment_ms":round((time.perf_counter()-enrichment_started)*1000),
                    "meter_roles":role_diagnostic,
                    "inventory_devices":len(audit_devices),
                    "inventory_complete":inventory_provenance.get("complete") is True,
                }
                if role_diagnostic.get("outcome")=="unavailable":
                    result["answer"]["validation_issues"].append(
                        "optional_measurement_role_enrichment_unavailable"
                    )
                return result
            if semantic is not None and semantic.mode in ("unsupported","historical"):
                # Unsupported whole-house history must not be misrepresented
                # as a present-state inventory query or fabricated timeline.
                subject=("A cross-device historical comparison" if
                         semantic.mode=="historical" else "This question")
                message=(subject+" is not yet supported by the safe V2 "
                         "inventory executor. Current inventory answers and "
                         "single-device investigation are available; no "
                         "device state was changed.")
                return {
                    "answer_mode":"semantic_unavailable",
                    "answer":{"text":message,"displayed_record_ids":[],
                              "omitted_material_record_ids":[],
                              "validation_issues":["unsupported_evidence_objective"],
                              "root_cause_verified":False,"human_review_required":True},
                    "report":{"text":message,"technical_answer_retained":False},
                    "semantic_plan":semantic.to_dict(),
                    "resolved_devices":[],"resolution_method":"semantic_objective",
                    "elapsed_ms":round((time.perf_counter()-started)*1000),
                    "test_mode":"explicit_read_only",
                }
        try:
            # Named historical cases retain the existing strict read plan.
            # Device identities may come from the *model's phrase*, but only
            # live Hubitat names/IDs can satisfy the host verification gate.
            devices = (audit_devices if audit_devices is not None
                       else await mcp.get_cached_devices(refresh=True))
            if payload.device_ids or payload.device_name:
                # Explicit operator overrides keep their strict verification.
                ids, resolved, resolve_method = resolve_verified_device_subjects(
                    payload.question, devices, device_name=payload.device_name,
                    device_ids=payload.device_ids)
            else:
                # An AI name proposal must not override a clear name in the
                # question. Live Hubitat identity remains authoritative.
                ids, resolved, resolve_method = resolve_planned_device_subjects(
                    payload.question, devices,
                    model_device_name=(semantic.device_name if semantic is not None
                                       and semantic.scope=="named" else None))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        except Exception:
            raise HTTPException(status_code=503, detail="Hubitat identity verification unavailable") from None
        # Hub time is obtained from existing authoritative resolver. If
        # unavailable, do not silently invent a calendar: use UTC and show
        # the fallback basis in the explicit window metadata.
        zone_name = "UTC"
        if re.search(r"\d{1,2}\s*(?:-|–|—|to)\s*\d{1,2}\s+[A-Za-z]+\s+\d{4}|\b(?:today|yesterday)\b",
                     payload.question, re.I):
            try:
                _now_local, resolved_zone, _zone_basis = await _health_timezone.now_in_hub_timezone(
                    lambda: datetime.now(timezone.utc))
                if resolved_zone:
                    zone_name = resolved_zone
            except Exception:
                pass
        incident_window = explicit_incident_window(
            payload.question, zone_name=zone_name,
            now=datetime.now(timezone.utc),
        )
        try:
            evaluated = await evaluate_v2_with_model(
                explicitly_authorised=True,
                question=payload.question,
                chat=agent.transport.chat,
                mcp=mcp, executor=agent.executor,
                verified_entity_ids=ids,
                enable_atomic_claim_validation=True,
                enable_evidence_narrative=True,
                bootstrap_device_context=True,
                semantic_unavailable_reason=semantic_failure,
                max_rounds=3, max_total_reads=8,
                incident_window=incident_window,
                verified_device_label=resolved[0]["label"] if len(resolved)==1 else None,
                force_duration_mode=semantic is not None and semantic.mode=="duration",
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Opt-in V2 evaluation unavailable")
            raise HTTPException(status_code=503, detail="V2 evaluation failed; no Hubitat writes attempted") from None
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        result = evaluated.to_dict()
        result["elapsed_ms"] = elapsed_ms
        result["test_mode"] = "explicit_read_only"
        result["resolved_devices"] = resolved
        result["resolution_method"] = resolve_method
        if semantic_failure is not None:
            result["answer_mode"] = "semantic_fallback_investigation"
            result["semantic_diagnostics"] = {
                "phase": "host_only_evidence_recovery",
                "outcome": "partial_evidence_recovered",
                "reason": semantic_failure,
                "inventory_ms": inventory_ms,
                "planning_ms": planning_ms,
                "inventory_devices": len(audit_devices),
                "inventory_complete": inventory_provenance.get("complete") is True,
                "target_verified": True,
                "model_investigation_attempted": False,
            }
        if semantic is not None:
            result["semantic_plan"] = semantic.to_dict()
            result["answer_mode"] = ("semantic_duration" if semantic.mode=="duration"
                                    else "semantic_investigation")
        result["scorecard"] = replay_scorecard(
            evaluated.investigation.case, evaluated.answer,
            existing_v1_answer=payload.existing_v1_answer,
            reference_answer=payload.reference_answer,
            reads_executed=evaluated.investigation.executed_reads,
            elapsed_ms=elapsed_ms,
        )
        return result

    # Separate coordinator key: never cancel or reuse a production chat.
    return await request_coordinator.run(
        "investigation-v2-test-exclusive", experiment(),
        connection=connection, request_id=uuid.uuid4().hex,
        deadline_seconds=240,
    )


@app.post("/api/chat")
async def chat(request: ChatRequest, connection: Request) -> dict[str, Any]:
    return {"response": await _answer(request, connection)}


@app.post("/api/ask")
async def ask(request: ChatRequest, connection: Request) -> dict[str, Any]:
    started = time.perf_counter()
    outcome = await _answer_result(request, connection)
    result = build_agent_response(
        outcome,
        model=agent.model_name,
        elapsed_ms=round((time.perf_counter() - started) * 1000),
        version=VERSION,
    )
    result["model_tier_requested"] = request.model_tier
    return result


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8788, log_level="info", proxy_headers=True)
