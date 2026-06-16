import argparse
import sys
from tfsensor_crew.crew import TfsensorCrew

def run():
    """
    Run the crew.
    """
    parser = argparse.ArgumentParser(description="Tfsensor CrewAI Status Aggregator")
    parser.add_argument('--progress', default='PROGRESS.md', help='Path to PROGRESS.md')
    parser.add_argument('--registry', default='JOBS_REGISTRY.csv', help='Path to JOBS_REGISTRY.csv')
    parser.add_argument('--output', default='sync_report.md', help='Output path for report')
    args = parser.parse_args()
    
    print("Starting Tfsensor Crew status synchronization...")
    try:
        crew_instance = TfsensorCrew()
        inputs = {
            'progress_path': args.progress,
            'registry_path': args.registry,
            'output_path': args.output
        }
        report = crew_instance.kickoff(inputs=inputs)
        print(f"Sync complete. Report written to {args.output}")
    except Exception as e:
        print(f"Error executing status crew: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    run()
