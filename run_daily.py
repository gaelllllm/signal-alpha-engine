import subprocess
import logging
import os
from datetime import datetime
from pathlib import Path

Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    filename=f"logs/run_{datetime.now().strftime('%Y%m%d')}.log",
    level=logging.INFO,
    format="%(asctime)s — %(message)s"
)


def run(script):
    print(f"\nRunning {script}...")
    logging.info(f"Starting {script}")
    result = subprocess.run(["py", script], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        logging.error(f"{script} failed: {result.stderr}")
        print(f"ERROR: {result.stderr}")
        return False
    logging.info(f"{script} completed")
    return True


if __name__ == "__main__":
    print("=" * 40)
    print(f"Signal Alpha Engine — Daily Run")
    print(f"{datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 40)

    # step 1 — update data
    if not run("data_pipeline.py"):
        exit(1)

    # step 2 — retrain on 1st of month, otherwise load saved model
    if datetime.now().day == 1:
        print("\nFirst of the month — forcing model retrain...")
        logging.info("Monthly retrain triggered")
        if os.path.exists("model.pkl"):
            os.remove("model.pkl")
            print("  model.pkl deleted — will retrain")

    if not run("model.py"):
        exit(1)

    # step 3 — update backtest and dashboard data
    run("backtest.py")

    # step 4 — place orders on Alpaca
    run("trader.py")

    print("\n" + "=" * 40)
    print("Daily run complete.")
    print(f"Signals updated at {datetime.now().strftime('%H:%M')}")
    logging.info("Daily run complete")