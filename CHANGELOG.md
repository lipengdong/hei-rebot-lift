# Changelog

All notable changes to HEI ReBot Lift are documented here. Project releases use
Git tags such as `v0.1.0` and `v0.2.0`. The version in
`software/lerobot-hei-rebot-lift/pyproject.toml` is the bundled LeRobot package
version and is intentionally managed separately.

## [0.2.0] - 2026-10-10

### Added

- Added an explicit HEI project version in `VERSION` and an upstream baseline
  record in `software/lerobot-hei-rebot-lift/UPSTREAM.md`.
- Added the `hei_rebot_lift` dependency extra and the
  `hei-rebot-lift-host` console entry point.
- Added compatibility decoding for both the new multipart observation protocol
  and the legacy Base64 JSON protocol.

### Changed

- Synchronized the software foundation with LeRobot `0.6.2`, upstream commit
  `b9cb121cb7d4e3e26ec5c906d08dda68d151ba52`.
- Migrated HEI recording, evaluation, robot registration, policy processing,
  datasets, training, and rollout integrations to the latest LeRobot APIs.
- Changed Host camera transport to a compact JSON state header followed by raw
  JPEG frames, reducing CPU and network overhead.
- Updated `lerobot-find-cameras` to use MJPG `640x480@30` by default and verify
  multiple OpenCV cameras concurrently.
- Updated English, Chinese, French, and Spanish deployment documentation.
- Replaced obsolete generated requirements files with dependency definitions in
  `pyproject.toml`.

### Compatibility

- Preserves the 18-dimensional HEI state/action layout.
- Preserves the `front`, `left_wrist`, and `right_wrist` camera feature names.
- Existing MuJoCo datasets and ACT checkpoints remain loadable.

## [0.1.0] - 2026-10-09

- First public HEI ReBot Lift baseline.
- Includes the dual-arm robot driver, lift and omnidirectional chassis control,
  VR/MuJoCo IK workflows, keyboard simulation, data recording, ACT/VLA examples,
  hardware BOM, CAD/STEP resources, wiring notes, and deployment guides.

[0.2.0]: https://github.com/lipengdong/hei-rebot-lift/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/lipengdong/hei-rebot-lift/releases/tag/v0.1.0
