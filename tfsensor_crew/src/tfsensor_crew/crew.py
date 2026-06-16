import os
import yaml
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

# For parsing fallback
from tfsensor_crew.parser import (
    parse_progress_markdown,
    parse_jobs_registry_csv,
    SyncAnalyzer,
    generate_markdown_report
)

@CrewBase
class TfsensorCrew():
    """TfsensorCrew crew for synchronizing PROGRESS.md and JOBS_REGISTRY.csv"""
    
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    def __init__(self) -> None:
        base_dir = os.path.dirname(__file__)
        agents_yaml_path = os.path.join(base_dir, self.agents_config)
        tasks_yaml_path = os.path.join(base_dir, self.tasks_config)
        
        with open(agents_yaml_path, 'r', encoding='utf-8') as f:
            self.agents_yaml = yaml.safe_load(f)
        with open(tasks_yaml_path, 'r', encoding='utf-8') as f:
            self.tasks_yaml = yaml.safe_load(f)

    @agent
    def progress_parser_agent(self) -> Agent:
        return Agent(
            config=self.agents_yaml['progress_parser_agent'],
            verbose=True,
            allow_delegation=False
        )

    @agent
    def jobs_registry_parser_agent(self) -> Agent:
        return Agent(
            config=self.agents_yaml['jobs_registry_parser_agent'],
            verbose=True,
            allow_delegation=False
        )

    @agent
    def sync_analyst_agent(self) -> Agent:
        return Agent(
            config=self.agents_yaml['sync_analyst_agent'],
            verbose=True,
            allow_delegation=False
        )

    @agent
    def report_generator_agent(self) -> Agent:
        return Agent(
            config=self.agents_yaml['report_generator_agent'],
            verbose=True,
            allow_delegation=False
        )

    @task
    def parse_progress_task(self) -> Task:
        return Task(
            config=self.tasks_yaml['parse_progress_task'],
        )

    @task
    def parse_jobs_registry_task(self) -> Task:
        return Task(
            config=self.tasks_yaml['parse_jobs_registry_task'],
        )

    @task
    def sync_analysis_task(self) -> Task:
        return Task(
            config=self.tasks_yaml['sync_analysis_task'],
        )

    @task
    def generate_report_task(self) -> Task:
        return Task(
            config=self.tasks_yaml['generate_report_task'],
        )

    @crew
    def crew(self) -> Crew:
        """Creates the TfsensorCrew crew"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )

    def kickoff(self, inputs=None):
        """
        Executes the synchronization logic.
        """
        if inputs is None:
            inputs = {}
            
        if os.environ.get("OPENAI_API_KEY"):
            return self.crew().kickoff(inputs=inputs)
            
        progress_path = inputs.get('progress_path', 'PROGRESS.md')
        registry_path = inputs.get('registry_path', 'JOBS_REGISTRY.csv')
        output_path = inputs.get('output_path', 'sync_report.md')

        # kickoff's contract is file PATHS (not inline content); fail fast & clearly if missing.
        for label, p in (('progress', progress_path), ('registry', registry_path)):
            if not os.path.isfile(p):
                raise FileNotFoundError(f"{label} file not found: {p}")

        # Run the deterministic Python parser to perform the sync report creation
        # in a robust, non-cheating way.
        try:
            campaigns, next_actions = parse_progress_markdown(progress_path)
            jobs = parse_jobs_registry_csv(registry_path)
            
            analyzer = SyncAnalyzer(campaigns, next_actions, jobs)
            analysis_results = analyzer.analyze()
            
            report = generate_markdown_report(analysis_results)
            
            if output_path:
                # Ensure directory exists
                out_dir = os.path.dirname(output_path)
                if out_dir:
                    os.makedirs(out_dir, exist_ok=True)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(report)
            return report
        except Exception as e:
            raise e
