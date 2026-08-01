<h1 align="center">HEI ReBot Lift</h1>

<p align="center">
  <img src="media/Repository-Header-Image.jpg" alt="HEI ReBot Lift" width="100%">
</p>

<p align="center">
  <a href="README.md"><b>English</b></a> <b>|</b>
  <a href="README_zh.md"><b>中文</b></a> <b>|</b>
  <a href="README_Fr.md"><b>français</b></a> <b>|</b>
  <a href="README_es.md"><b>Español</b></a>
</p>

<p align="center">
  <a href="https://github.com/lipengdong/hei-rebot-lift/stargazers">
    <img src="https://img.shields.io/github/stars/lipengdong/hei-rebot-lift?style=social" alt="GitHub stars">
  </a>
</p>

## 🚀 Présentation

**HEI ReBot Lift** est un projet de **robot mobile à double bras avec plateforme élévatrice**, conçu pour l'apprentissage de l'IA incarnée, la reproduction matérielle et la validation sur robot réel. Son objectif est de **réduire la barrière d'entrée pour construire de vrais systèmes d'apprentissage robotique**. Le projet suit l'idée d'un **open source réellement reproductible** : non seulement le code est publié, mais aussi les ressources matérielles, les étapes de câblage, le déploiement, la téléopération VR, l'enregistrement de données, l'entraînement ACT/VLA et le rollout sur robot réel.

<p align="center">
  <b>🚀 Manipulation mobile à double bras</b> · <b>📖 Matériel + logiciel ouverts</b> · <b>🤖 Compatible LeRobot</b>
</p>

<p align="center">
  <a href="#-installation-rapide">🚀 Installation rapide</a> ·
  <a href="#-matériel">🦾 Matériel</a> ·
  <a href="#-démarrage">🎮 Téléopération VR</a> ·
  <a href="#-enregistrement-des-données">📷 Données</a> ·
  <a href="#-entraînement-act">🧠 ACT</a> ·
  <a href="#-entraînement-smolvla">✨ VLA</a>
</p>

## ✨ Points forts

<div align="center">

<table>
  <thead>
    <tr><th align="center">Icône</th><th align="center">Capacité</th><th align="center">Description</th></tr>
  </thead>
  <tbody>
    <tr><td align="center">🦾</td><td align="center">Manipulation à double bras</td><td align="center">Deux bras Damiao et pinces pour téléopération, enregistrement et rollout de politiques</td></tr>
    <tr><td align="center">⬆️</td><td align="center">Plateforme élévatrice</td><td align="center">Homing automatique au démarrage, limite haute définie comme <code>height.pos = 0</code></td></tr>
    <tr><td align="center">⭕</td><td align="center">Base omnidirectionnelle</td><td align="center">Châssis omnidirectionnel à quatre roues avec contrôle <code>x/y/theta</code></td></tr>
    <tr><td align="center">🎮</td><td align="center">Téléopération VR</td><td align="center">Telegrip reçoit les contrôleurs VR ; MuJoCo + Pinocchio/CasADi calculent l'IK</td></tr>
    <tr><td align="center">📷</td><td align="center">Trois caméras</td><td align="center"><code>front</code>, <code>left_wrist</code> et <code>right_wrist</code></td></tr>
    <tr><td align="center">🧠</td><td align="center">Apprentissage par imitation / VLA</td><td align="center">Prend en charge LeRobotDataset, ACT, SmolVLA et rollout sur robot réel</td></tr>
  </tbody>
</table>

<img src="media/hei-robot-lift-play.gif" alt="Démonstration HEI ReBot Lift" width="60%">

</div>

## 🤝 Obtenir votre robot / Rejoindre la communauté

Vous pouvez reproduire votre propre **HEI ReBot Lift** à partir des ressources matérielles, du BOM, des notes de câblage et de la documentation de déploiement. Nous accueillons aussi les échanges autour de la manipulation mobile à double bras, de la téléopération VR, de la collecte de données LeRobot, de l'entraînement ACT/VLA et du déploiement sur robot réel.

<p align="center">
  <b>Communauté WeChat / collaboration :</b> <code>hgm159951</code> &nbsp;&nbsp;|&nbsp;&nbsp;
  <b>Email :</b> <a href="mailto:hgm159951@163.com">hgm159951@163.com</a>
</p>

## 📁 Structure du projet

```text
hei-rebot-lift/
├── README.md
├── README_zh.md
├── README_Fr.md
├── README_es.md
├── community/
├── hardware/
├── media/
├── docs/
└── software/
    └── lerobot-hei-rebot-lift/
```

Le logiciel exécutable se trouve dans :

```bash
cd software/lerobot-hei-rebot-lift
```

## 🦾 Matériel

| Ressource | Fichier / Dossier | Description |
| --- | --- | --- |
| Guide matériel | [hardware/README.md](hardware/README.md) | Index matériel, ordre de reproduction et checklist de sécurité |
| BOM complet | [hardware/HEI_ReBot_Lift_BOM.md](hardware/HEI_ReBot_Lift_BOM.md) / [xlsx](hardware/HEI_ReBot_Lift_BOM.xlsx) | Liste principale d'achat et de préparation |
| Assemblage complet | [hardware/Hei_robot_lift.STEP](hardware/Hei_robot_lift.STEP) | Modèle STEP complet du robot |
| Pièces imprimées 3D | [hardware/3D_Printed_Parts/](hardware/3D_Printed_Parts/) | Fichiers STL |
| Liste des pièces métalliques | [hardware/Metal_Parts/HEI_Metal_Body_Parts_List.xlsx](hardware/Metal_Parts/HEI_Metal_Body_Parts_List.xlsx) | Liste CNC / tôlerie |
| CAD métalliques | [hardware/Metal_Parts/step/](hardware/Metal_Parts/step/) / [hardware/Metal_Parts/dwg/](hardware/Metal_Parts/dwg/) | STEP et DWG |

```text
Bras : deux bras, 7 moteurs Damiao chacun. Joints 1-3 : DM4340P ; joints 4-6 et pince : DM4310
Châssis : base mobile omnidirectionnelle à quatre roues, moteurs DM4310
Élévateur : plateforme à vis avec moteur DM4310, homing vers height.pos = 0
Caméras : front, left_wrist, right_wrist
Communication : ZMQ entre le host robot et le client PC
Téléopération : casque VR + contrôleurs, Telegrip, MuJoCo, Pinocchio/CasADi
```

## ⚡ Installation rapide

Créer l'environnement LeRobot :

```bash
cd software/lerobot-hei-rebot-lift
conda create -n lerobot5 python=3.12 -y
conda activate lerobot5
pip install -e .
```

Créer l'environnement VR/MuJoCo IK :

```bash
cd software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik
conda env create -f environment.yml
```

Vérifier Pinocchio + CasADi :

```bash
conda activate hei-rebot-vr
env -u LD_LIBRARY_PATH python -c "import pinocchio as pin; from pinocchio import casadi as cpin; print(pin.__version__); print('casadi binding ok')"
```

## 🔌 Mappage des périphériques

```text
/dev/hei_right_arm   Bras droit U2CAN
/dev/hei_left_arm    Bras gauche U2CAN
/dev/hei_chassis     Châssis U2CAN
/dev/hei_lift        Moteur élévateur U2CAN
/dev/hei_lift_io     Port série des fins de course
```

## 🎮 Démarrage

Côté robot :

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 hei-rebot-lift-host
```

Côté ordinateur, lancer Telegrip :

```bash
cd software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik
./run_telegrip.sh
```

Lancer MuJoCo IK :

```bash
cd software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik
./run_mujoco_ik.sh
```

Test de téléopération :

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/teleoperate.py --remote-ip 192.168.31.127
```

## 📷 Enregistrement des données

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/record.py --repo-id HGM/hei_rebot_lift_task1 --remote-ip 192.168.31.127 --num-episodes 5 --episode-time-sec 120 --reset-time-sec 30 --task-description "Pick up the yellow block from the floor and put it on the table in front"
```

## 🧠 Entraînement ACT

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-train --dataset.repo_id=HGM/hei_rebot_lift_task1 --policy.type=act --policy.device=cuda --policy.push_to_hub=false --output_dir=outputs/train/act_hei_rebot_lift_task1 --job_name=act_hei_rebot_lift_task1 --batch_size=8 --steps=10000 --save_freq=10000 --log_freq=200 --num_workers=4 --wandb.enable=false
```

## ✨ Entraînement SmolVLA

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-train --dataset.repo_id=HGM/hei_rebot_lift_task1 --policy.type=smolvla --policy.device=cuda --policy.push_to_hub=false --output_dir=outputs/train/smolvla_hei_rebot_lift_task1 --job_name=smolvla_hei_rebot_lift_task1 --batch_size=1 --steps=1000 --save_freq=1000 --log_freq=50 --num_workers=2 --wandb.enable=false
```

## 🤖 Rollout sur robot réel

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/rollout.py --model-id outputs/train/act_hei_rebot_lift_task1/checkpoints/010000/pretrained_model --task "Pick up the yellow block from the floor and put it on the table in front" --duration-sec 30 --inference sync
```

## ⭐ Star History

<p align="center">
  <a href="https://www.star-history.com/?repos=lipengdong%2Fhei-rebot-lift&type=date&legend=top-left">
    <img src="media/star-history-2026731.png" alt="HEI ReBot Lift Star History" width="72%">
  </a>
</p>

## 🙏 Références

- [Seeed reBot-DevArm](https://github.com/Seeed-Projects/reBot-DevArm)
- [LeRobot](https://github.com/huggingface/lerobot)
