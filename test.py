from datetime import datetime, timedelta
import pytz

eastern = pytz.timezone("US/Eastern")
today = datetime.now(eastern)
end_of_day = today + timedelta(days=0.75)

print(today.isoformat())
print(end_of_day.isoformat())