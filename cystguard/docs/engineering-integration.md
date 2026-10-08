# Engineering integration

Details will be filled progressively.

## Branch and PR rules
1. Nobody directly works on main for feature implementation.
2. Use feature/jaiganesh-ml, feature/aditya-trust-ocr, feature/rohith-backend, feature/roshan-frontend.
3. Every meaningful change goes through a pull request.
4. PRs identify what changed, files changed, API contract impact, integration dependencies, and tests performed.
5. Document frontend changes requiring backend work.
6. Backend request/response changes update backend schema, frontend type, API contract, affected tests, and change-log.
7. Do not silently rename API fields.
8. Coordinate before modifying another owner subsystem.
9. Use mocks/fixtures while another subsystem is unavailable.
10. Integrate through documented contracts, not assumptions.

## PR checklist
- [ ] Feature/change described
- [ ] Files changed listed
- [ ] Owner identified
- [ ] API contract affected? Yes/No
- [ ] If yes, api-contract.md updated
- [ ] Frontend types updated if required
- [ ] Backend schemas updated if required
- [ ] Tests added/updated
- [ ] Security implications checked
- [ ] Clinical safety implications checked
- [ ] Change-log updated
- [ ] Integration dependency documented
- [ ] CI passes
