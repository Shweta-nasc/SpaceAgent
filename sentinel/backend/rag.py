from typing import Any, Dict

# Standard ECSS procedure snippets
ECSS_PROCEDURES = {
    "eps": (
        "ECSS-E-ST-20C (Space Engineering - Electrical Power):\n"
        "- Clause 5.3.2.1: Under-voltage protection shall isolate non-essential loads when battery voltage (V_bat) drops below 22.0V or State of Charge (SoC) drops below 15%.\n"
        "- Clause 5.3.4.3: If solar array current (I_sa) drops to 0A while spacecraft is in sunlight, the driver power board shall be reset via CMD_SOLAR_ARRAY_A_RESET. Verify array current recovery before reconnecting loads."
    ),
    "adcs": (
        "ECSS-E-ST-60-30C (Space Engineering - Attitude and Orbit Control):\n"
        "- Section 6.4.1 (Sensor Fault Recovery): If a gyroscope returns a constant value, NaN, or out-of-bounds rate, the FDIR system shall isolate the sensor and command a warm reset using CMD_GYRO_A_RESET.\n"
        "- Section 6.4.2: Wait 30 seconds after reset for sensor calibration. If Gyro_rate remains invalid, disable the primary sensor and command switchover to backup unit (Gyro B) using CMD_SWITCH_TO_GYRO_B."
    ),
    "obc": (
        "ECSS-E-ST-70-01C (Space Engineering - On-board Software):\n"
        "- Section 7.2.5 (Watchdog Recovery): Watchdog timers shall reset the computer upon overflow (Watchdog_counter > 1000). The boot loader shall initialize in SAFE MODE and reset the watchdog counter.\n"
        "- Section 7.2.6: If a thread hang is diagnosed (CPU load = 100%), execute CMD_OBC_PROCESS_RESTART to clear the process list and restore nominal thread scheduling."
    ),
    "tcs": (
        "ECSS-E-ST-31C (Space Engineering - Thermal Control):\n"
        "- Clause 4.2.1: If component temperatures exceed nominal operating range, verify heater status and flags. If the primary heater fails to activate, command the backup heater zone using CMD_TCS_HEATER_ON."
    ),
    "comms": (
        "ECSS-E-ST-50C (Space Engineering - Communications):\n"
        "- Section 5.1.2: Upon loss of transponder lock status, point the high-gain antenna to Earth. If alignment fails, switch to the low-gain omnidirectional antenna."
    ),
}

class LlamaIndexPipeline:
    def __init__(self, index_path: str = "", config: Dict[str, Any] | None = None):
        self.index_path = index_path
        self.config = config or {}

    def query(self, text: str) -> str:
        """Search the local ECSS procedures database based on keyword matching."""
        query_lower = text.lower()
        matched_procedures = []

        # Simple keyword matching
        if any(k in query_lower for k in ["gyro", "adcs", "attitude", "star tracker", "sensor"]):
            matched_procedures.append(ECSS_PROCEDURES["adcs"])
        if any(k in query_lower for k in ["power", "eps", "battery", "voltage", "solar", "v_bat", "i_sa"]):
            matched_procedures.append(ECSS_PROCEDURES["eps"])
        if any(k in query_lower for k in ["obc", "watchdog", "cpu", "memory", "software", "loop", "thread"]):
            matched_procedures.append(ECSS_PROCEDURES["obc"])
        if any(k in query_lower for k in ["thermal", "temp", "heater", "tcs"]):
            matched_procedures.append(ECSS_PROCEDURES["tcs"])
        if any(k in query_lower for k in ["comms", "communication", "antenna", "signal", "transponder"]):
            matched_procedures.append(ECSS_PROCEDURES["comms"])

        # Fallback to general ECSS context if no specific matches found
        if not matched_procedures:
            return "No specific ECSS procedures matched the query. Relying on default FDIR guidelines."

        return "\n\n---\n\n".join(matched_procedures)
