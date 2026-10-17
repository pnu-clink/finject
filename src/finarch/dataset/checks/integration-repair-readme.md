# Generation check code repair

This is a modification of the check input, time value, and output method. The actual generating and judgment logic, the source code, and past execution results have not changed. 0calls.

|Item|Changes and verification|
|---|---|
|EA default operation|The current mandatory digestive regression test is to make sure that it's recorded separately from the old optional test setting.|
|EA's restoration judgment|The existing Q/C proof-of-concept input verifies the recoverable judgment and the proof.|
|EA is underestimating|If there's no valid connection, record NOT_EVALUATED and why, and check to see if it's keeping up with the existing PASS/FAIL and why.|
|IC-RELATION|First, we create a temporary folder and we set up a check entry without any previous run, and then we check if the final answer is the same after the Python graph-correct contrast, and we check if it blocks the candidate registration.|
|IC-SOURCE|So you call the module to import_module, and then you use patch.object, and you keep the folder name.|
|Additional check-in correction|Remove unused fact, and differentiate the total input hash change from the actual inverse result and near-invariance following a private record change.|

The result: **{count}passed**Running time. {seconds}Second, this is a local test, and FinanceReasoning is not the actual API execution or overall production success rate.

In order of reading: this document → integration-repair-checks.json → integration- repair.log. In the common viewer, you can open the back-end integration check box for this run to see the current results. legacy-integration.log keeps the error record before the correction.

Responsibility: `checks/test_ea_recovery.py`, `test_generation_python_gates.py`The EA and the SOURCE judge check the operation. `test_relation_plan.py`The temporary input and the candidate registration scale, `test_source_from_value.py`Just check that the source phrase is added to the source from VALUE. Both are Python checks and do not actually call LLM.
