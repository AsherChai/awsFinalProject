import boto3
import json
from decimal import Decimal
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')

def lambda_handler(event, context):
    print("🔎 Event:", json.dumps(event))

    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    path = event.get("rawPath", "")
    query = event.get("queryStringParameters", {})

    # 🔁 טיפול ב-OPTIONS (Preflight)
    if method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,Authorization",
                "Access-Control-Allow-Methods": "GET,OPTIONS"
            }
        }

    game_id = query.get("GameID")
    if not game_id:
        return respond(400, {"error": "Missing GameID in query string"})

    if "/results/players" in path:
        table_name = "PlayerStats"
        key_name = "GameID"
    elif "/results/teams" in path:
        table_name = "TeamStats"
        key_name = "GameID"
    else:
        return respond(404, {"error": "Unknown path"})

    try:
        table = dynamodb.Table(table_name)
        response = table.query(
            KeyConditionExpression=Key(key_name).eq(game_id)
        )
        return respond(200, convert_decimal(response["Items"]))
    except Exception as e:
        print("❌ Error:", str(e))
        return respond(500, {"error": str(e)})

def respond(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,OPTIONS"
        },
        "body": json.dumps(body)
    }

def convert_decimal(obj):
    if isinstance(obj, list):
        return [convert_decimal(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return float(obj) if '.' in str(obj) else int(obj)
    else:
        return obj
