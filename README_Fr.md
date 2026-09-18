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

## Feuille de route et dernières avancées

Le tableau présente l'état actuel du projet et les liens vers la documentation associée. Les guides techniques liés sont disponibles en anglais, avec des versions chinoises pour la plupart.

| Module | État | Avancées actuelles | Documentation |
| --- | --- | --- | --- |
| Structure du robot | Première version terminée | Double bras, plateforme élévatrice et base omnidirectionnelle à quatre roues en configuration O intégrés et testés ensemble | [Matériel](hardware/README.md) |
| URDF du robot complet | Terminé | Modèle du châssis, des roues, de l'élévateur, des bras, des pinces parallèles et des repères TCP pour la simulation et l'IK sur robot réel | [Modèle URDF](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/mujoco_ik/model/HEI_robot_urdf/) |
| Tests de simulation MuJoCo | Terminés | Contrôle VR des bras, pinces, élévateur et châssis testé, avec animation des roues, projection dans l'espace de travail et démonstrations de prise et dépose en mode de préhension stable | [Guide de simulation](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/README.md) |
| Pilote des moteurs Damiao | Première version terminée | `damiao_u2can` contrôle les bras, pinces, moteurs du châssis et de l'élévateur | [Damiao U2CAN](software/lerobot-hei-rebot-lift/src/lerobot/motors/damiao_u2can/) |
| Plateforme élévatrice | Première version terminée | Homing sur la limite haute au démarrage et commande de position cible `height.pos` | [Pilote du robot](software/lerobot-hei-rebot-lift/src/lerobot/robots/hei_rebot_lift/README.md) · [Contrôle indépendant de l'élévateur](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README.md#independent-lift-test) |
| Base omnidirectionnelle | Première version terminée | Commandes `x.vel`, `y.vel` et `theta.vel`, avec lissage de l'accélération et de la décélération | [Pilote du robot](software/lerobot-hei-rebot-lift/src/lerobot/robots/hei_rebot_lift/README.md) · [Contrôle indépendant du châssis](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README.md#independent-chassis-test) |
| Vision à trois caméras | Première version terminée | Caméras OpenCV `front`, `left_wrist` et `right_wrist`, au format MJPG par défaut | [Pilote du robot](software/lerobot-hei-rebot-lift/src/lerobot/robots/hei_rebot_lift/README.md) |
| VR et IK MuJoCo | Première version terminée | Telegrip, MuJoCo et Pinocchio/CasADi reliés à la chaîne de contrôle du robot réel | [VR MuJoCo IK](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/README.md) |
| Intégration LeRobot | Première version terminée | Robot, client et host `hei_rebot_lift`, avec scripts de téléopération, enregistrement, replay, évaluation et rollout | [Exemples](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README.md) |
| Collecte de données | Première version terminée | Enregistrement LeRobotDataset, reprise, visualisation et suppression des épisodes de mauvaise qualité | [Guide d'enregistrement](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README.md) |
| Entraînement et rollout ACT | Vérifiés | Entraînement ACT et rollout sur robot réel | [Exemples](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README.md) |
| SmolVLA / VLA | Support initial | Points d'entrée pour l'entraînement SmolVLA et le rollout sur robot réel | [Exemples](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README.md) |
| Ressources matérielles ouvertes | Terminées | BOM global, assemblage STEP complet, pièces imprimées STL, liste des pièces métalliques et fichiers STEP/DWG de fabrication | [Matériel](hardware/README.md) |
| Communauté et reproduction | En cours | Groupe WeChat, contact par e-mail et dépôt GitHub disponibles | [Communauté](community/README.md) |
| Reproduction d'autres VLA populaires | À venir | Reproduire et tester d'autres politiques VLA pour l'entraînement, l'inférence et le déploiement sur HEI ReBot Lift | Non terminé |

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

**Chaque bloc commence dans un nouveau terminal à la racine du dépôt, sur la
machine indiquée. Ne pas exécuter toutes les étapes sur une seule machine.**
`lerobot5` utilise Python 3.12; `hei-rebot-vr` utilise Python 3.10 comme défini
dans `environment.yml`. Ce sont deux environnements aux rôles différents.

### 1. Jetson du robot : pilotes matériels

```bash
cd software/lerobot-hei-rebot-lift
conda create -n lerobot5 python=3.12 -y
conda activate lerobot5
python -m pip install -e ".[hardware,pyzmq-dep]"
python -c "import serial, zmq, cv2; print('robot dependencies ok')"
```

Réutiliser l'environnement s'il existe déjà. Les dépendances de base incluent
PyTorch; ce n'est pas un paquet matériel autonome. En cas de conflit sur Jetson,
vérifier JetPack et les contraintes PyTorch/torchvision du projet; ne pas copier
des roues CUDA de PC ni ignorer toutes les dépendances avec `--no-deps`.
Ne pas installer l'environnement VR/IK sur le robot.

### 2. Ordinateur : contrôle, données et entraînement

```bash
cd software/lerobot-hei-rebot-lift
conda create -n lerobot5 python=3.12 -y
conda activate lerobot5
python -m pip install -e ".[core_scripts,training,pyzmq-dep]"
python -m pip show pyzmq rerun-sdk pynput datasets accelerate
```

Les extras installent les outils de données, Rerun, clavier, ZMQ et entraînement
général. SmolVLA exige en plus son extra, indiqué ci-dessous.

### 3. Ordinateur : VR et MuJoCo IK

```bash
cd software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik
conda env create -f environment.yml
conda activate hei-rebot-vr
env -u LD_LIBRARY_PATH python -c "import pinocchio as pin; from pinocchio import casadi as cpin; print(pin.__version__); print('casadi binding ok')"
```

Pour une mise à jour, remplacer la création par
`conda env update -n hei-rebot-vr -f environment.yml --prune`.
Pinocchio/CasADi/eigenpy/coal-python doivent venir de conda-forge selon ce fichier;
ne pas installer `pin` séparément avec pip. Les scripts activent automatiquement
`hei-rebot-vr` et ceux de MuJoCo effacent `LD_LIBRARY_PATH`.

## 🔌 Mappage des périphériques

```text
/dev/hei_right_arm   Bras droit U2CAN
/dev/hei_left_arm    Bras gauche U2CAN
/dev/hei_chassis     Châssis U2CAN
/dev/hei_lift        Moteur élévateur U2CAN
/dev/hei_lift_io     Port série des fins de course
```

### 1. Identification et liaison des ports

Sur le Jetson, arrêter le host et tous les outils série. Couper l'alimentation
et soutenir les bras avant de changer le câblage. Débrancher temporairement les
moteurs **4-7 du bras droit** (ne garder que 1-3); laisser le bras gauche 1-7, le
châssis 1-4 et l'élévateur 1 branchés. Alimenter les quatre U2CAN, moteurs et IO
pour la détection. L'assistant [Port_Binding_Wizard.py](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/debug/Port_Binding_Wizard.py) ne commande aucun mouvement
et n'écrit aucun zéro.

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/debug/Port_Binding_Wizard.py
```

Confirmer les résultats avant d'écrire les règles; installation système avec
sudo. Les règles lidar/IMU existantes sont conservées. Garder les mêmes prises
USB: la liaison suit la topologie physique. Vérifier les cinq liens, couper
l'alimentation, puis reconnecter les moteurs droits 4-7 avant les tests.
`--yes --install` est réservé aux répétitions déjà vérifiées.

### 2. Tests indépendants après la liaison

Arrêter le host, utiliser un seul outil série à la fois et garder l'arrêt
d'urgence accessible. Activer `lerobot5` et lancer directement Python dans un
terminal interactif (SSH avec TTY). Les détails sont dans le
[guide matériel indépendant](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README.md#1-hardware-check).

- **Zéros des bras :** le script désactive et écrit immédiatement les zéros des sept moteurs, sans confirmation. Soutenir le bras, le placer au zéro mécanique de conception, pince fermée à `0 rad`; une pose VR quelconque n'est pas un zéro. Ce n'est pas un outil de lecture seule.

<p align="center">
  <a href="media/arm_zero.png"><img src="media/arm_zero.png" alt="Posture de zéro mécanique des deux bras" width="70%"></a>
  <br>
  <em>Référence du zéro mécanique de conception. Vérifier chaque articulation selon le plan d'assemblage avant d'écrire les zéros; ce n'est pas la posture de travail VR.</em>
</p>

- **Élévateur :** `debug/Lift_Status_Test.py --height-step-mm 2` effectue un homing automatique vers le haut. Vérifier les deux fins de course. `I/K` modifie la cible de 2 mm par événement, `Space` maintient la hauteur mesurée, `H` refait le homing, `X` quitte. Plage `-800..0 mm`.
- **Châssis :** `debug/Chassis_Status_Test.py`, roues solidement suspendues. `W/S/A/D` translation, `Q/E` rotation, `1/2/3` vitesses, `Space` vitesse nulle, `X` quitte. Commencer à 1. Les quatre roues bougent ensemble; pas de mode roue individuelle. IDs 1 avant droit, 2 arrière droit, 3 arrière gauche, 4 avant gauche; timeout clavier 0.65 s.

### 3. Caméras

Vérifier sur le **robot**: `front=/dev/video0`, `left_wrist=/dev/video2`,
`right_wrist=/dev/video4`; profils actuels `640x480 @ 30 FPS`, `MJPG`.
Les noms de périphériques peuvent varier. Lancer `lerobot-find-cameras` sur le
robot. Le flux vidéo VR est actuellement désactivé, pas la capture du host.

Sur le **Jetson du robot**, arrêter le host et l'outil de recherche, puis modifier
[config_hei_rebot_lift.py](software/lerobot-hei-rebot-lift/src/lerobot/robots/hei_rebot_lift/config_hei_rebot_lift.py), fonction
`hei_rebot_lift_cameras_config()`. Identifier les caméras avec les images de
`outputs/captured_images` et remplacer les trois valeurs `index_or_path`.
Conserver les clés `front`, `left_wrist`, `right_wrist` et les autres réglages;
ne pas modifier `camera_opencv.py` ni le YAML VR pour ces IDs USB.
Enregistrer et redémarrer `hei-rebot-lift-host`. Sur l'ordinateur client,
conserver les mêmes clés et dimensions; les périphériques USB sont ouverts
sur le robot. Après reconnexion USB, vérifier les IDs à nouveau.
[Exemple de configuration](software/lerobot-hei-rebot-lift/src/lerobot/robots/hei_rebot_lift/README.md#where-to-change-camera-ids).

## 🎮 Démarrage

| Adresse d'exemple | Machine | Usage |
| --- | --- | --- |
| `192.168.31.245` | Ordinateur de contrôle | Casque: `https://192.168.31.245:8443` |
| `192.168.31.127` | Jetson du robot | Client: `--remote-ip`; caméras VR: `tcp://192.168.31.127:6556` |
| `localhost / 127.0.0.1` | Machine exécutant le programme | Connexions locales Telegrip/IK/client |

Remplacer chaque adresse par celle de sa machine. Le casque utilise l'IP de
l'ordinateur, **pas celle du robot**. Les machines doivent pouvoir communiquer
sur le LAN. Le paramètre `--remote-ip` ne modifie pas `telegrip/config.yaml`.

### 1. Pratiquer en simulation avant le robot réel

<p align="center"><img src="media/robot-mujoco.png" alt="Simulation HEI ReBot Lift" width="85%"></p>

Sur l'ordinateur uniquement; **ne pas lancer le host, teleoperate, record ou le
pont réel**. Terminal A:

```bash
cd software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik
./run_telegrip.sh
```

Ouvrir `https://192.168.31.245:8443` dans le casque, vérifier l'adresse avant
d'accepter le certificat autosigné, puis entrer en VR. Terminal B séparé:

```bash
cd software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik
./run_hei_robot_vr_sim.sh
```

La fenêtre MuJoCo est sur l'ordinateur: robot complet, roues animées, sol,
lumières, table, cubes et banane locale. Aucun ordre réel sur 6558.
La préhension stable attache les objets au TCP; ce n'est pas une validation de
la physique de contact. Les limites/projections IK ne détectent pas les collisions.

#### 1.1 Boutons et calibration de l'origine

<table align="center">
  <tr>
    <td align="center"><a href="media/META-QUEST-BUTTON.jpg"><img src="media/META-QUEST-BUTTON.jpg" alt="Meta Quest" width="200"></a><br>Meta Quest</td>
    <td align="center"><a href="media/META-GRIP-BUTTON.jpg"><img src="media/META-GRIP-BUTTON.jpg" alt="Grip" width="200"></a><br>Grip</td>
    <td align="center"><a href="media/META-FRONT-TRIGGER.jpg"><img src="media/META-FRONT-TRIGGER.jpg" alt="Trigger" width="200"></a><br>Trigger</td>
  </tr>
</table>

> [!IMPORTANT]
> **Maintenir le META QUEST BUTTON du contrôleur droit environ 3 secondes pour recentrer le repère VR sur la position et l'orientation actuelles du casque.**
> **Recalibrer après un changement de position ou de direction, ou si les mouvements du bras et du contrôleur ne suivent pas la même direction.**
> Relâcher les deux grips, centrer les sticks, faire face à la direction voulue, maintenir le bouton environ 3 secondes, attendre la stabilisation puis reprendre grip. Vérifier avec un petit mouvement.

Le recentrage du casque diffère de l'origine relative capturée par grip.
Il ne calibre pas les zéros moteurs et ne remplace pas le homing de l'élévateur.

| Entrée | Condition | Fonction |
| --- | --- | --- |
| Grip gauche/droit | Maintenu | Contrôle relatif du bras correspondant, déplacement et rotation à échelle 1:1 dans la zone atteignable |
| Trigger | Grip correspondant maintenu | Appuyer pour ouvrir, relâcher pour fermer; relâcher grip conserve le dernier état de la pince |
| Stick gauche vertical | Grip gauche maintenu | Avancer pour monter, reculer pour descendre |
| Stick droit | Grip droit maintenu | Avancer/reculer et translation latérale |
| B droit / Y gauche | Grip droit maintenu | Rotation horaire / antihoraire |
| A droit / X gauche | Grip correspondant relâché | Retour progressif du bras à sa pose par défaut |
| F / R dans MuJoCo | Fenêtre active | Repères / réinitialisation de la simulation; R est désactivé en mode réel |

Relâcher le grip droit/gauche annule la demande de mouvement châssis/élévateur;
le freinage réel dépend du matériel. Pratiquer chaque bras, la pince, le
recentrage et l'arrêt avant la suite. Fermer la simulation; Telegrip peut rester
ouvert. La vitesse d'élévation simulée (0.20 m/s) n'est pas celle du matériel.

### 2. Jetson : démarrer le host

Terminer les vérifications matérielles, fermer les outils de debug, dégager
l'espace et attendre **la fin du homing automatique vers le haut**.

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 hei-rebot-lift-host
```

Garder ce terminal ouvert sur le robot.

### 3. Ordinateur : démarrer le contrôle réel

#### 3.1 Telegrip et casque

Démarrer `run_telegrip.sh` comme ci-dessus, sauf s'il tourne déjà, et ouvrir
l'adresse **de l'ordinateur** dans le casque. Pour activer les images, régler
`vr_images.enabled: true` et `vr_images.endpoint: tcp://192.168.31.127:6556`
dans `telegrip/config.yaml`, puis redémarrer Telegrip et recharger le casque.
Cela utilise l'IP **du robot** et ne change pas ses caméras de capture.

#### 3.2 Client avec l'IP du robot

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/teleoperate.py --remote-ip 192.168.31.127
```

#### 3.3 Pont réel du modèle complet

```bash
cd software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik
./run_hei_robot_vr_real.sh --enable-real-publish
```

Avec des données VR et un retour robot frais, **relâcher les deux grips ensemble**
et attendre `command bridge ARMED`. Le drapeau autorise la publication sans
contourner la synchronisation. Ne pas utiliser `--allow-no-feedback` pour
résoudre un problème réseau. `run_mujoco_ik.sh` est l'ancien modèle double bras,
pas cette entrée; ne jamais lancer les deux ponts ensemble.

Un host robot et trois programmes ordinateur. VR et retour robot expirent chacun
après 1 s; le host a aussi un watchdog de commandes de 1000 ms. Après récupération,
relâcher les grips pour resynchroniser et réarmer. Ces protections ne remplacent
pas l'arrêt d'urgence. Le viewer réel n'affiche que le robot; sa vitesse
d'élévation ~0.0286 m/s est un plafond théorique, pas un retour mesuré continu.

## 📷 Enregistrement des données

Arrêter teleoperate; record le remplace et publie le retour sur 6559. Garder
host, Telegrip et pont réel; relâcher les grips pour réarmer après reconnexion.

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/record.py --repo-id HGM/hei_rebot_lift_task1 --remote-ip 192.168.31.127 --num-episodes 5 --episode-time-sec 120 --reset-time-sec 30 --task-description "Pick up the yellow block from the floor and put it on the table in front"
```

Sauvegarde locale par défaut; ajouter `--push-to-hub` uniquement pour téléverser.
Reprise (cinq épisodes supplémentaires):

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/record.py --repo-id HGM/hei_rebot_lift_task1 --remote-ip 192.168.31.127 --root ~/.cache/huggingface/lerobot/HGM/hei_rebot_lift_task1 --resume --num-episodes 5
```

Utiliser le chemin réel affiché dans les logs; conserver noms de caméras,
dimensions et FPS. Après changement de schéma, créer un nouveau dataset.
Pour visualiser ou supprimer des épisodes, consulter le
[guide des données](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README.md#6-visualize-and-clean-data).
Sauvegarder avant suppression; les indices commencent à zéro et sont renumérotés.

## 🧠 Entraînement ACT

Sur l'ordinateur, sans host ni VR. Si le dossier est personnalisé, ajouter
`--dataset.root=CHEMIN_REEL` avec l'identifiant exact. Les runs courts vérifient
la chaîne, pas la qualité finale de la politique.

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-train --dataset.repo_id=HGM/hei_rebot_lift_task1 --policy.type=act --policy.device=cuda --policy.push_to_hub=false --output_dir=outputs/train/act_hei_rebot_lift_task1 --job_name=act_hei_rebot_lift_task1 --batch_size=8 --steps=10000 --save_freq=10000 --log_freq=200 --num_workers=4 --wandb.enable=false
```

## ✨ Entraînement SmolVLA

Installer d'abord ses dépendances, non incluses dans l'extra training général:

```bash
cd software/lerobot-hei-rebot-lift
conda run --no-capture-output -n lerobot5 python -m pip install -e ".[smolvla]"
```

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 lerobot-train --dataset.repo_id=HGM/hei_rebot_lift_task1 --policy.type=smolvla --policy.device=cuda --policy.push_to_hub=false --output_dir=outputs/train/smolvla_hei_rebot_lift_task1 --job_name=smolvla_hei_rebot_lift_task1 --batch_size=1 --steps=1000 --save_freq=1000 --log_freq=50 --num_workers=2 --wandb.enable=false
```

Les premières exécutions peuvent télécharger le backbone et le tokenizer.
Le mode hors ligne exige tous les fichiers nécessaires déjà en cache.

## 🤖 Rollout sur robot réel

Garder le host, mais arrêter pont VR, teleoperate, record et replay avant
l'inférence. **Un seul contrôleur à la fois.** Vérifier checkpoint, caméras,
texte de tâche et espace de travail; commencer par un test court.

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/rollout.py --remote-ip 192.168.31.127 --model-id outputs/train/act_hei_rebot_lift_task1/checkpoints/010000/pretrained_model --task "Pick up the yellow block from the floor and put it on the table in front" --duration-sec 30 --inference sync
```

SmolVLA:

```bash
cd software/lerobot-hei-rebot-lift
PYTHONPATH=src conda run --no-capture-output -n lerobot5 python -u examples/hei_rebot_lift/rollout.py --remote-ip 192.168.31.127 --model-id outputs/train/smolvla_hei_rebot_lift_task1/checkpoints/001000/pretrained_model --task "Pick up the yellow block from the floor and put it on the table in front" --duration-sec 60 --fps 10 --inference rtc
```

`--fps` modifie la cadence d'exécution, pas la vitesse de calcul du modèle.
Voir le [guide replay et evaluate](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README.md#10-replay-and-evaluate):
replay reproduit les actions; evaluate exécute ACT et enregistre de nouveaux
épisodes, sans calcul automatique du taux de réussite.

## Documentation complémentaire

- [Index des guides](docs/README.md)
- [Contrôle, données et entraînement](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/README.md)
- [Paramètres du robot, unités et watchdog](software/lerobot-hei-rebot-lift/src/lerobot/robots/hei_rebot_lift/README.md)
- [VR, contrôleurs et dépannage](software/lerobot-hei-rebot-lift/examples/hei_rebot_lift/VR_mujoco_ik/README.md)

## ⭐ Star History

<p align="center">
  <a href="https://www.star-history.com/?repos=lipengdong%2Fhei-rebot-lift&type=date&legend=top-left">
    <img src="media/star-history-2026731.png" alt="HEI ReBot Lift Star History" width="72%">
  </a>
</p>

## 🙏 Références

- [Seeed reBot-DevArm](https://github.com/Seeed-Projects/reBot-DevArm)
- [LeRobot](https://github.com/huggingface/lerobot)


## Licence

Le logiciel est basé sur LeRobot. Consulter [LICENSE](LICENSE) et respecter les licences des dépendances et ressources tierces, notamment les ressources YCB.
