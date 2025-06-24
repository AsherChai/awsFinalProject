import boto3
import json
from decimal import Decimal
from datetime import datetime

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
runtime = boto3.client('sagemaker-runtime')
ses = boto3.client('ses', region_name='us-east-1')  # ✅ חדש – SES client

player_table = dynamodb.Table('PlayerStats')
team_table = dynamodb.Table('TeamStats')
insights_table = dynamodb.Table('GameInsights')

SENDER_EMAIL = 'rubinasher@gmail.com'  # ✅ כתובת מאומתת ב-SES
RECIPIENT_EMAIL = 'rubinasher@gmail.com'  # או כתובת המאמן (אם מאומתת)


def lambda_handler(event, context):
    print("✅ Lambda Triggered")

    try:
        bucket = event['Records'][0]['s3']['bucket']['name']
        uploaded_key = event['Records'][0]['s3']['object']['key']
        prefix = '/'.join(uploaded_key.split('/')[:-1])
        print(f"📁 Prefix: {prefix}")

        player = try_load_json(bucket, f"{prefix}/player.json")
        team = try_load_json(bucket, f"{prefix}/team.json")

        if player is None or team is None:
            print("⚠️ אחד הקבצים לא קיים או לא נטען כראוי")
            return {"status": "missing files"}

        game_id = str(player.get('playlistId', 'UNKNOWN'))
        print(f"🎮 GameID: {game_id}")

        all_players_for_sagemaker = []

        # שחקנים
        for team_name, team_players in player['teams'].items():
            for p in team_players:
                try:
                    athlete_id = str(p['id'])
                    base = {
                        'GameID': game_id,
                        'AthleteID': athlete_id,
                        'Name': p.get('name', 'Unknown'),
                        'TeamName': p.get('teamName', ''),
                        'Started': p.get('started', False)
                    }
                    stats = {}
                    config = p.get('data', {}).get('configuration', [])[0].get('configuration', [])
                    for stat in config:
                        stats[stat.get('abbreviation', 'Unknown')] = stat.get('value')

                    item = {**base, **stats}
                    print(f"🟢 Writing player {athlete_id}")
                    player_table.put_item(Item=item)
                    all_players_for_sagemaker.append(item)

                except Exception as e:
                    print(f"❌ שגיאה בשחקן {p.get('id')}: {str(e)}")

        # קבוצות
        for team_type in ['home', 'away']:
            try:
                team_id = str(team.get(f"{team_type}TeamId", 'NA'))
                team_name = team.get(f"{team_type}TeamName", 'NA')
                stats = {}
                for group in team.get('configuration', []):
                    for stat in group.get('configuration', []):
                        abbr = stat.get('abbreviation', 'Unknown')
                        value = stat.get(f"{team_type}TeamValue")
                        stats[abbr] = value

                item = {
                    'GameID': game_id,
                    'TeamID': team_id,
                    'TeamName': team_name,
                    **stats
                }
                print(f"🔵 Writing team {team_id}")
                team_table.put_item(Item=item)

            except Exception as e:
                print(f"❌ שגיאה בקבוצה {team_type}: {str(e)}")

        # תובנות
        # call_sagemaker_and_save_insights(game_id, all_players_for_sagemaker)

        # ✅ שליחת מייל דרך SES
        try:
            ses.send_email(
                Source=SENDER_EMAIL,
                Destination={'ToAddresses': [RECIPIENT_EMAIL]},
                Message={
                    'Subject': {'Data': f'📥 משחק חדש הועלה ({game_id})'},
                    'Body': {
                        'Text': {
                            'Data': f'הועלה משחק חדש למערכת CoachAI עם מזהה: {game_id}.\n\n'
                                    f'קבצים הועלו לנתיב: {prefix}\n\n'
                                    'לצפייה בנתוני המשחק היכנס למערכת בקישור הבא:\n'
                                    'https://coachai-game-uploads.s3.us-east-1.amazonaws.com/index.html'
                        }
                    }
                }
            )
            print("📨 Email sent via SES.")
        except Exception as ses_error:
            print(f"⚠️ SES email send failed: {ses_error}")

        return {'status': 'success'}

    except Exception as e:
        print(f"❌ GENERAL ERROR: {str(e)}")
        raise

    # פונקציה לטעינת קובץ JSON מ-S3


def try_load_json(bucket, key):
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        return json.loads(response['Body'].read().decode('utf-8'))
    except Exception as e:
        print(f"⚠️ Failed to load {key}: {e}")
        return None
