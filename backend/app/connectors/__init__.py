"""Data gathering. Owner: A.

Pattern: every source has ONE active connector chosen by env (CONNECTOR_<SOURCE>=mock|<real>).
Connectors return list[ConnectorEnvelope]; ingest.py is the only thing that writes their output to the repo.
Swapping mock -> real changes nothing outside this folder.
"""
