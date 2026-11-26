"""Run a SQL query on Athena and return rows as dictionaries."""
import time

from agent.aws import session

OUTPUT = "s3://provenance-data-4102a6/athena-results/"


def run_query(sql, database="provenance", output=OUTPUT):
    client = session().client("athena")
    qid = client.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": database},
        ResultConfiguration={"OutputLocation": output},
    )["QueryExecutionId"]

    while True:
        status = client.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"]
        if status["State"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(1)
    if status["State"] != "SUCCEEDED":
        raise RuntimeError(status.get("StateChangeReason", status["State"]))

    rows, header = [], None
    for page in client.get_paginator("get_query_results").paginate(QueryExecutionId=qid):
        for row in page["ResultSet"]["Rows"]:
            values = [c.get("VarCharValue") for c in row["Data"]]
            if header is None:
                header = values
            else:
                rows.append(dict(zip(header, values)))
    return rows
