import urllib.request
import json
import re

url = "https://news.google.com/rss/articles/CBMi4gFBVV95cUxNdVM5VTMtdkI2WWpSc0pzQ3psMjI5UnlHZzVMMWZ4WmNzTGdQX3NaX0VTRFgwOGV4RlZjZk5wLWpXTXEySDZOSU5hc21lSElTREZzRUNTajFuWWN0ZDdmakNLc2I3UlRfdlpGbnJiWllQczkxNDJURFRNRHZEY2JyRHV4RFNjdEdWUHFGVmJwUnFBckhXc1pBRWVUaEYyWkdleS1ZVktQa1ZpTTJHam4zbnptRWpPa0t4YXJHVHJvUkhGSmtOMWpKdWJXSm5sUTlLRzVscmhzWl9DM2l6czVfNHBR?oc=5"

req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req, timeout=10) as response:
        html = response.read().decode('utf-8', errors='ignore')
        # find real redirect url or text
        print("Final URL:", response.geturl())
        # extract title / text
        m = re.findall(r'<p[^>]*>(.*?)</p>', html)
        for p in m[:10]:
            print("P:", p[:200])
except Exception as e:
    print("Error:", e)
