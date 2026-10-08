# Shared API contract

Authoritative contract between frontend and backend. Frontend never guesses backend data. Backend never assumes frontend requirements. Both follow the shared API contract.

No endpoints or response structures are defined yet. Detailed implementation will be filled progressively. Backend schemas: backend/app/schemas/. Frontend types: frontend/src/types/.

Every contract change updates backend schema, frontend type, this document, affected tests, and change-log. Do not silently rename fields.
