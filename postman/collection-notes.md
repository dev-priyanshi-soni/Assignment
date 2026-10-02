# Postman

Create:

POST http://127.0.0.1:8000/api/v1/route/optimize/

Body -> raw -> JSON:

{
  "start": "New York, NY",
  "finish": "Chicago, IL"
}

Demo examples:
1. New York, NY -> Chicago, IL
2. Los Angeles, CA -> Las Vegas, NV
3. A long-distance route that requires multiple fuel stops.
