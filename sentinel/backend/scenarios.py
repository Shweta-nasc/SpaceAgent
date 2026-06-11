import datetime

def get_preset_scenarios():
    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    
    return [
        {
            "scenario_id": 1,
            "timestamp": now,
            "fault_type": "ADCS_SENSOR_FAULT",
            "fault_register": "0x00000080",
            "pre_fault_telemetry": [
                {"parameter": "Gyro_rate_degs", "value": "NaN", "nominal_min": 0.0, "nominal_max": 7.0},
                {"parameter": "Attitude_error_deg", "value": 7.3, "nominal_min": 0.0, "nominal_max": 0.01},
                {"parameter": "SEU_counter", "value": 3.0, "nominal_min": 0.0, "nominal_max": 0.0},
                {"parameter": "RW_speed_rpm", "value": 4500.0, "nominal_min": -6000.0, "nominal_max": 6000.0},
                {"parameter": "V_bat", "value": 30.2, "nominal_min": 28.0, "nominal_max": 33.6},
                {"parameter": "SoC_pct", "value": 85.0, "nominal_min": 20.0, "nominal_max": 100.0},
                {"parameter": "I_sa", "value": 8.4, "nominal_min": 0.0, "nominal_max": 12.0},
                {"parameter": "OBC_temp_C", "value": 24.5, "nominal_min": -10.0, "nominal_max": 60.0}
            ],
            "event_log": [
                {"timestamp": "T-62s", "source": "OBC_KERNEL", "message": "SEU counter incremented: 3"},
                {"timestamp": "T-60s", "source": "ADCS_MANAGER", "message": "GYRO_A health status: NaN"},
                {"timestamp": "T-30s", "source": "ADCS_ATTITUDE", "message": "Attitude error exceeded threshold (7.3 deg)"},
                {"timestamp": "T-0s", "source": "FDIR_CORE", "message": "Safe Mode entry triggered by ADCS_ERROR"}
            ],
            "hardware_state": {
                "active_gyro": "A",
                "seu_flags": "0x03",
                "watchdog_status": "nominal"
            },
            "operating_context": {
                "eclipse_fraction": 0.0,
                "sun_sensor_angle_deg": 12.5,
                "time_since_contact_s": 1200
            }
        },
        {
            "scenario_id": 2,
            "timestamp": now,
            "fault_type": "EPS_POWER_FAULT",
            "fault_register": "0x00000002",
            "pre_fault_telemetry": [
                {"parameter": "I_sa", "value": 0.0, "nominal_min": 0.0, "nominal_max": 12.0},
                {"parameter": "V_bat", "value": 21.8, "nominal_min": 28.0, "nominal_max": 33.6},
                {"parameter": "SoC_pct", "value": 14.2, "nominal_min": 20.0, "nominal_max": 100.0},
                {"parameter": "V_bus", "value": 24.1, "nominal_min": 26.6, "nominal_max": 29.4},
                {"parameter": "Heater_power_W", "value": 15.0, "nominal_min": 0.0, "nominal_max": 50.0},
                {"parameter": "Attitude_error_deg", "value": 0.004, "nominal_min": 0.0, "nominal_max": 0.01},
                {"parameter": "OBC_temp_C", "value": 18.2, "nominal_min": -10.0, "nominal_max": 60.0}
            ],
            "event_log": [
                {"timestamp": "T-300s", "source": "EPS_SENSORS", "message": "Solar Array A Current dropped to 0A (expected: 8.5A)"},
                {"timestamp": "T-180s", "source": "EPS_MANAGER", "message": "State of Charge low (14.2%). Starting load shedding."},
                {"timestamp": "T-120s", "source": "OBC_CORE", "message": "Command issued: Power off PYLD subsystem"},
                {"timestamp": "T-0s", "source": "FDIR_CORE", "message": "Safe Mode entry triggered by EPS_UNDER_VOLT"}
            ],
            "hardware_state": {
                "solar_relay": "open",
                "battery_relays": "closed",
                "shed_status": "active"
            },
            "operating_context": {
                "eclipse_fraction": 0.0,
                "sun_sensor_angle_deg": 42.0,
                "time_since_contact_s": 2400
            }
        },
        {
            "scenario_id": 3,
            "timestamp": now,
            "fault_type": "OBC_SOFTWARE_FAULT",
            "fault_register": "0x00000040",
            "pre_fault_telemetry": [
                {"parameter": "CPU_load_pct", "value": 100.0, "nominal_min": 0.0, "nominal_max": 70.0},
                {"parameter": "Memory_usage_MB", "value": 495.0, "nominal_min": 0.0, "nominal_max": 500.0},
                {"parameter": "Watchdog_counter", "value": 1002.0, "nominal_min": 0.0, "nominal_max": 1000.0},
                {"parameter": "V_bat", "value": 31.1, "nominal_min": 28.0, "nominal_max": 33.6},
                {"parameter": "SoC_pct", "value": 90.0, "nominal_min": 20.0, "nominal_max": 100.0},
                {"parameter": "Attitude_error_deg", "value": 0.003, "nominal_min": 0.0, "nominal_max": 0.01}
            ],
            "event_log": [
                {"timestamp": "T-180s", "source": "OBC_MONITOR", "message": "CPU load exceeded 95%"},
                {"timestamp": "T-120s", "source": "OBC_MONITOR", "message": "Memory leak signature detected in thread 'attitude_control'"},
                {"timestamp": "T-10s", "source": "WATCHDOG_TIMER", "message": "Watchdog counter exceeded limit (value=1002)"},
                {"timestamp": "T-0s", "source": "OBC_BOOT", "message": "Watchdog reset triggered. Booting in Safe Mode."}
            ],
            "hardware_state": {
                "watchdog_state": "expired",
                "active_bank": "EEPROM_B",
                "last_reboot_cause": "WATCHDOG_RESET"
            },
            "operating_context": {
                "eclipse_fraction": 0.2,
                "sun_sensor_angle_deg": 15.0,
                "time_since_contact_s": 50
            }
        }
    ]
