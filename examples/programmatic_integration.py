"""Example: Programmatic Integration (Inline Workflow)

This example demonstrates how a developer would integrate Stoa into an 
existing Python application (like a FastAPI backend or a portfolio site)
without needing external YAML files.
"""

from stoa.runner import WorkflowRunner

def main():
    # 1. Initialize the runner
    runner = WorkflowRunner()

    print("--- Running Inline Task ---")
    
    # 2. Define a task and run it directly
    # In this scenario, we imagine a portfolio site verifying experience
    result = runner.run_inline(
        name="portfolio_verification",
        task="""
        From the provided projects list, find all projects that involve 'FastAPI'.
        Return a list of project names.
        """,
        inputs={
            "projects": [
                {"name": "Stoa", "tech": ["Python", "FastAPI"]},
                {"name": "VoiceVerdict", "tech": ["Firebase", "TypeScript"]},
                {"name": "TailorForge", "tech": ["Python", "FastAPI", "Next.js"]},
            ]
        }
    )

    # 3. Handle the result
    if result.success:
        print(f"Success! Output: {result.output}")
        print(f"Tokens Used: {result.tokens_used}")
        print(f"Execution Cost: ${result.cost_usd:.4f}")
    else:
        print(f"Failed: {result.error}")

if __name__ == "__main__":
    main()
