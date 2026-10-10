"""Approval queue transitions and sending. Owner: C.
INVARIANT: nothing is sent unless a human moved the draft to `approved`. Enforced in send_draft().
"""
