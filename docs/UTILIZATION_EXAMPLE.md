# SIMULATED EXAMPLE FROM TEST FIXTURES, not measured data

This document reproduces selected room-utilization test fixtures. The values are
simulation examples only; they are not measured occupancy, detection accuracy,
energy measurements, or verified savings.

The default classification thresholds are configurable defaults, not measured
baselines: under 40% is underutilized, 40% through 90% is balanced/well
utilized, and above 90% is overutilized. These defaults require future
measurement before use as measured targets.

Energy savings are **Not measured** in every endpoint example.

## Underutilized

Input fixture:

- Classroom: `Room 101`
- Capacity: `100`
- Completed lectures: `3`
- Accessible classrooms: `2`
- Average occupied students across lectures: `30`
- Average utilization: `30%`
- Peak occupancy: `30`

Endpoint response:

```json
{
  "classroom_id": 101,
  "classroom_name": "Room 101",
  "capacity": 100,
  "from_date": null,
  "to_date": null,
  "lecture_count": 3,
  "average_occupancy": 30.0,
  "peak_occupancy": 30,
  "peak_time": "2030-01-01T10:00:00Z",
  "utilization_percent": 30.0,
  "exit_count": 0,
  "unused_minutes": 0.0,
  "unused_periods": [],
  "classification": "underutilized",
  "simulated": true,
  "suggestion": "Room 101 average utilization is 30%; consider reviewing room size and scheduling. Occupancy data can support resource optimization.",
  "status": "underutilized",
  "recommendations": [
    "Simulated resource optimization suggestion: review scheduling for Room 101; it is used at 30% average utilization."
  ],
  "energy_savings": "Not measured"
}
```

## Balanced

Input fixture:

- Classroom: `Room 101`
- Capacity: `100`
- Completed lectures: `3`
- Accessible classrooms: `2`
- Average occupied students across lectures: `60`
- Average utilization: `60%`
- Peak occupancy: `60`

Endpoint response:

```json
{
  "classroom_id": 101,
  "classroom_name": "Room 101",
  "capacity": 100,
  "from_date": null,
  "to_date": null,
  "lecture_count": 3,
  "average_occupancy": 60.0,
  "peak_occupancy": 60,
  "peak_time": "2030-01-01T10:00:00Z",
  "utilization_percent": 60.0,
  "exit_count": 0,
  "unused_minutes": 0.0,
  "unused_periods": [],
  "classification": "well_utilized",
  "simulated": true,
  "suggestion": "Room 101 average utilization is 60%. Occupancy data can support resource optimization.",
  "status": "balanced",
  "recommendations": [
    "Simulated resource optimization suggestion: continue the existing schedule for Room 101; average utilization is 60%."
  ],
  "energy_savings": "Not measured"
}
```

## Overutilized

Input fixture:

- Classroom: `Room 101`
- Capacity: `100`
- Completed lectures: `3`
- Accessible classrooms: `2`
- Average occupied students across lectures: `95`
- Average utilization: `95%`
- Peak occupancy: `95`

Endpoint response:

```json
{
  "classroom_id": 101,
  "classroom_name": "Room 101",
  "capacity": 100,
  "from_date": null,
  "to_date": null,
  "lecture_count": 3,
  "average_occupancy": 95.0,
  "peak_occupancy": 95,
  "peak_time": "2030-01-01T10:00:00Z",
  "utilization_percent": 95.0,
  "exit_count": 0,
  "unused_minutes": 0.0,
  "unused_periods": [],
  "classification": "overutilized",
  "simulated": true,
  "suggestion": "Room 101 average utilization is 95%; consider reviewing room capacity and scheduling. Occupancy data can support resource optimization.",
  "status": "overutilized",
  "recommendations": [
    "Simulated resource optimization suggestion: review capacity or scheduling for Room 101; it is used at 95% average utilization."
  ],
  "energy_savings": "Not measured"
}
```

## Not Enough Data

Input fixture:

- Classroom: `Room 101`
- Capacity: `100`
- Completed lectures: `1`
- Accessible classrooms: `2`
- Average occupied students: `30`
- Average utilization: `30%`

The recommendation threshold is also based on the configured minimum of two
completed lectures.

Endpoint response:

```json
{
  "classroom_id": 101,
  "classroom_name": "Room 101",
  "capacity": 100,
  "from_date": null,
  "to_date": null,
  "lecture_count": 1,
  "average_occupancy": 30.0,
  "peak_occupancy": 30,
  "peak_time": "2030-01-01T10:00:00Z",
  "utilization_percent": 30.0,
  "exit_count": 0,
  "unused_minutes": 0.0,
  "unused_periods": [],
  "classification": "underutilized",
  "simulated": true,
  "suggestion": "Room 101 average utilization is 30%; consider reviewing room size and scheduling. Occupancy data can support resource optimization.",
  "status": "underutilized",
  "recommendations": [
    "Not enough data"
  ],
  "energy_savings": "Not measured"
}
```

## No Completed Lectures

No completed lecture data may be summarized as zero-data:

```json
{
  "classroom_id": 101,
  "classroom_name": "Room 101",
  "capacity": 100,
  "from_date": null,
  "to_date": null,
  "lecture_count": 0,
  "average_occupancy": 0.0,
  "peak_occupancy": 0,
  "peak_time": null,
  "utilization_percent": 0.0,
  "exit_count": 0,
  "unused_minutes": 0.0,
  "unused_periods": [],
  "classification": "no_data",
  "simulated": true,
  "suggestion": "Room 101 has no completed lecture occupancy data in this period. Occupancy data can support resource optimization when available.",
  "status": "no_data",
  "recommendations": [
    "Not enough data"
  ],
  "energy_savings": "Not measured"
}
```
