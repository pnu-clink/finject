# Dashboard shed project status and storage of experimental data

[Picture pipeline](../../../docs/03-dashboard/README.md) · [A whole source structure](../../../docs/01-dataset/90-operations/05-source-layout.md)

1. [01-data/data.py](01-data/data.py): Registered storage files; raw response connection; hash; review cache.
2. [02-metrics/metrics.py](02-metrics/metrics.py)I read the logged processing time, the perception, the token cost.
3. [03-project/monitor.py](03-project/monitor.py)It's a local session and a stored run-text that creates a project situation.](03-project/session-map.json)It's just a job classification.
4. [viewer/resources.py](viewer/resources.py): Only the permissible screen file, API and source references are provided.
5. [viewer/server.py](viewer/server.py): 8895 Independent server. [start.command](../../../viewer/dashboard/start.command)You open the browser together.

The screen file is in the [viewer/dashboard](../../../viewer/dashboard/README.md)Local investigators. `checks`The default address is the project status, and the experimental number screen keeps the path unchanged, not doing model calls or re-evaluating the prime numbers.
