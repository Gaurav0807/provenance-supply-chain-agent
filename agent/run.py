"""Ask the agent one question from the command line.

Usage (from the project root, with AWS_PROFILE set):
  python -m agent.run "Which factories are at risk?"
"""
import sys

from agent.graph import ask

if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or input("Question: ")
    result = ask(question)
    print(result["answer"])
    print("\nTools used:", [step["tool"] for step in result["trace"]] or "none")
