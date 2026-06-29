const state = {
  config: null,
  websocket: null,
  xrSession: null,
  brandHud: null,
  headText: null,
  image: {
    enabled: false,
    cameras: [],
    states: new Map(),
    panels: new Map(),
    opacity: 0.82,
    renderStarted: false
  }
};

function setStatus(message) {
  const statusText = document.getElementById('statusText');
  if (statusText) statusText.textContent = message;
}

function setServerUrl() {
  const serverUrl = document.getElementById('serverUrl');
  if (serverUrl) serverUrl.textContent = window.location.origin;
}

async function loadConfig() {
  const response = await fetch('/api/config');
  state.config = await response.json();
  const imageConfig = state.config?.vr_images || state.config?.vr_image || {};
  state.image.enabled = Boolean(imageConfig.enabled);
  state.image.opacity = Number.isFinite(Number(imageConfig.opacity)) ? Number(imageConfig.opacity) : 0.82;
  state.image.cameras = imageConfig.cameras || (imageConfig.image_key ? [{ id: 'front', ...imageConfig }] : []);
  return state.config;
}

function websocketUrl() {
  const port = state.config?.network?.websocket_port || 8442;
  return `wss://${window.location.hostname}:${port}`;
}

function connectWebSocket() {
  const url = websocketUrl();
  state.websocket = new WebSocket(url);
  state.websocket.onopen = () => setStatus(`VR data connected: ${url}`);
  state.websocket.onerror = () => setStatus('VR data connection error');
  state.websocket.onclose = () => setStatus('VR data disconnected');
}

function attachRigToCamera() {
  const rig = document.getElementById('cameraRig');
  const cameraEl = document.querySelector('a-scene')?.camera?.el;
  if (!rig || !cameraEl) return;
  if (rig.parentNode !== cameraEl) cameraEl.appendChild(rig);
  rig.setAttribute('position', '0 -0.08 -1.85');
}

function createTextHud() {
  const cameraEl = document.querySelector('a-scene')?.camera?.el;
  if (!cameraEl || state.headText) return;

  const text = document.createElement('a-text');
  text.setAttribute('value', 'Head: waiting...');
  text.setAttribute('position', '0 -0.38 -0.75');
  text.setAttribute('align', 'center');
  text.setAttribute('color', '#EAF4FF');
  text.setAttribute('width', '0.9');
  text.setAttribute('baseline', 'center');
  text.setAttribute('anchor', 'center');
  cameraEl.appendChild(text);
  state.headText = text;
}

function createBrandHud() {
  const rig = document.getElementById('cameraRig');
  if (!rig || state.brandHud) return;

  const group = document.createElement('a-entity');
  group.setAttribute('id', 'hgm-brand-hud');
  group.setAttribute('position', '0.72 0.88 0');

  const mark = document.createElement('a-text');
  mark.setAttribute('value', 'HGM');
  mark.setAttribute('align', 'center');
  mark.setAttribute('anchor', 'center');
  mark.setAttribute('baseline', 'center');
  mark.setAttribute('color', '#05070A');
  mark.setAttribute('width', '1.45');
  mark.setAttribute('position', '0 0 0');
  group.appendChild(mark);

  const subtitle = document.createElement('a-text');
  subtitle.setAttribute('value', 'VR Teleoperation');
  subtitle.setAttribute('align', 'center');
  subtitle.setAttribute('anchor', 'center');
  subtitle.setAttribute('baseline', 'center');
  subtitle.setAttribute('color', '#05070A');
  subtitle.setAttribute('width', '0.86');
  subtitle.setAttribute('position', '0 -0.12 0');
  group.appendChild(subtitle);

  rig.appendChild(group);
  state.brandHud = group;
}

function cameraId(cameraConfig) {
  return cameraConfig.id || cameraConfig.image_key || 'front';
}

function panelLayout(cameraIdValue) {
  if (cameraIdValue === 'front') return { x: 0, y: 0.16, width: 1.5, height: 1.12 };
  if (cameraIdValue === 'left_wrist') return { x: -1.1, y: -0.08, width: 0.76, height: 0.57 };
  if (cameraIdValue === 'right_wrist') return { x: 1.1, y: -0.08, width: 0.76, height: 0.57 };
  return { x: 0, y: -0.08, width: 0.76, height: 0.57 };
}

function createHiddenImageState(cameraConfig) {
  const id = cameraId(cameraConfig);
  const img = document.createElement('img');
  img.id = `${id}-camera-stream`;
  img.alt = `${id} ZMQ camera stream`;
  img.crossOrigin = 'anonymous';
  img.style.cssText = 'position:fixed;right:0;bottom:0;width:2px;height:2px;opacity:0.01;pointer-events:none;';

  const canvas = document.createElement('canvas');
  canvas.id = `${id}-camera-canvas`;
  canvas.width = cameraConfig.width || 640;
  canvas.height = cameraConfig.height || 480;
  canvas.style.cssText = img.style.cssText;

  document.body.appendChild(img);
  document.body.appendChild(canvas);

  state.image.states.set(id, {
    id,
    config: cameraConfig,
    img,
    canvas,
    ctx: canvas.getContext('2d'),
    texture: null
  });
}

function createCameraPanel(cameraConfig) {
  const rig = document.getElementById('cameraRig');
  if (!rig) return;

  const id = cameraId(cameraConfig);
  const layout = panelLayout(id);
  const panel = document.createElement('a-entity');
  panel.setAttribute('id', `${id}-camera-panel`);
  panel.setAttribute('position', `${layout.x} ${layout.y} 0`);

  const border = document.createElement('a-plane');
  border.setAttribute('width', (layout.width + 0.04).toFixed(2));
  border.setAttribute('height', (layout.height + 0.04).toFixed(2));
  border.setAttribute('color', '#202836');
  border.setAttribute('position', '0 0 -0.01');
  border.setAttribute('material', 'shader: flat; side: double');
  panel.appendChild(border);

  const screen = document.createElement('a-plane');
  screen.setAttribute('width', layout.width);
  screen.setAttribute('height', layout.height);
  screen.setAttribute('color', '#111111');
  screen.setAttribute('material', 'shader: flat; side: double');
  panel.appendChild(screen);

  const label = document.createElement('a-text');
  label.setAttribute('value', cameraConfig.name || id);
  label.setAttribute('align', 'center');
  label.setAttribute('color', '#FFFFFF');
  label.setAttribute('width', '1.6');
  label.setAttribute('position', `0 ${(layout.height / 2 + 0.1).toFixed(2)} 0`);
  panel.appendChild(label);

  const meta = document.createElement('a-text');
  meta.setAttribute('value', 'waiting...');
  meta.setAttribute('align', 'center');
  meta.setAttribute('color', '#B8C7D9');
  meta.setAttribute('width', '1.2');
  meta.setAttribute('position', `0 ${(-layout.height / 2 - 0.1).toFixed(2)} 0`);
  panel.appendChild(meta);

  rig.appendChild(panel);
  state.image.panels.set(id, { panel, screen, label, meta });
}

function applyCameraTexture(id) {
  const cameraState = state.image.states.get(id);
  const panel = state.image.panels.get(id);
  const mesh = panel?.screen?.getObject3D('mesh');
  if (!cameraState || !mesh) return;

  if (!cameraState.texture) {
    cameraState.texture = new THREE.CanvasTexture(cameraState.canvas);
    cameraState.texture.minFilter = THREE.LinearFilter;
    cameraState.texture.magFilter = THREE.LinearFilter;
    cameraState.texture.generateMipmaps = false;
    if ('colorSpace' in cameraState.texture && THREE.SRGBColorSpace) {
      cameraState.texture.colorSpace = THREE.SRGBColorSpace;
    }
    mesh.material = new THREE.MeshBasicMaterial({
      map: cameraState.texture,
      side: THREE.DoubleSide,
      toneMapped: false,
      transparent: state.image.opacity < 1,
      opacity: state.image.opacity,
      depthWrite: state.image.opacity >= 1
    });
  }
  cameraState.texture.needsUpdate = true;
}

function createAxisPart(type, attributes) {
  const el = document.createElement(type);
  Object.entries(attributes).forEach(([key, value]) => el.setAttribute(key, value));
  return el;
}

function addControllerAxes(handEl) {
  if (!handEl || handEl.querySelector('[data-telegrip-axis="true"]')) return;

  const axisLength = 0.11;
  const radius = 0.004;
  const tipHeight = 0.025;
  const tipRadius = 0.011;
  const axes = [
    {
      color: '#ff3b30',
      cylinder: { position: `${axisLength / 2} 0 0`, rotation: '0 0 90' },
      cone: { position: `${axisLength} 0 0`, rotation: '0 0 90' }
    },
    {
      color: '#34c759',
      cylinder: { position: `0 ${axisLength / 2} 0`, rotation: '0 0 0' },
      cone: { position: `0 ${axisLength} 0`, rotation: '0 0 0' }
    },
    {
      color: '#0a84ff',
      cylinder: { position: `0 0 ${axisLength / 2}`, rotation: '90 0 0' },
      cone: { position: `0 0 ${axisLength}`, rotation: '90 0 0' }
    }
  ];

  axes.forEach(axis => {
    const cylinder = createAxisPart('a-cylinder', {
      'data-telegrip-axis': 'true',
      height: axisLength,
      radius,
      color: axis.color,
      position: axis.cylinder.position,
      rotation: axis.cylinder.rotation
    });
    const cone = createAxisPart('a-cone', {
      'data-telegrip-axis': 'true',
      height: tipHeight,
      'radius-bottom': tipRadius,
      'radius-top': 0,
      color: axis.color,
      position: axis.cone.position,
      rotation: axis.cone.rotation
    });
    handEl.appendChild(cylinder);
    handEl.appendChild(cone);
  });
}

function renderCameraFrames() {
  if (!state.image.enabled) return;

  state.image.states.forEach((cameraState, id) => {
    const { img, canvas, ctx } = cameraState;
    if (!ctx || !img.complete || !img.naturalWidth || !img.naturalHeight) return;
    if (canvas.width !== img.naturalWidth || canvas.height !== img.naturalHeight) {
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
    }
    try {
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      applyCameraTexture(id);
    } catch (error) {
      console.warn(`Could not draw ZMQ camera frame for ${id}:`, error);
    }
  });

  window.requestAnimationFrame(renderCameraFrames);
}

async function setupOptionalCameraPanels() {
  if (!state.image.enabled) {
    setStatus('ZMQ image display disabled; VR data ready');
    return;
  }

  const cameras = state.image.cameras.filter(camera => camera.enabled !== false);
  cameras.forEach(camera => {
    createHiddenImageState(camera);
    createCameraPanel(camera);
  });

  cameras.forEach(camera => {
    const id = cameraId(camera);
    const cameraState = state.image.states.get(id);
    if (cameraState) {
      cameraState.img.src = `/api/camera/stream.mjpg?camera=${encodeURIComponent(id)}&ts=${Date.now()}`;
    }
  });

  await Promise.all(cameras.map(async camera => {
    const id = cameraId(camera);
    try {
      const status = await fetch(`/api/camera/status?camera=${encodeURIComponent(id)}`).then(response => response.json());
      const panel = state.image.panels.get(id);
      if (panel) panel.meta.setAttribute('value', `${status.width || 0}x${status.height || 0} | ${status.image_key || id}`);
    } catch (error) {
      console.warn(`Could not load ZMQ camera status for ${id}:`, error);
    }
  }));

  if (!state.image.renderStarted) {
    state.image.renderStarted = true;
    window.requestAnimationFrame(renderCameraFrames);
  }
}

function controllerData(handEl, hand, buttons) {
  const payload = {
    hand,
    position: null,
    rotation: null,
    quaternion: null,
    gripActive: buttons.grip,
    trigger: buttons.trigger ? 1 : 0,
    thumbstick: buttons.thumbstick || { x: 0, y: 0, pressed: 0 }
  };

  if (hand === 'left') {
    payload.xButton = buttons.x ? 1 : 0;
    payload.yButton = buttons.y ? 1 : 0;
  } else {
    payload.aButton = buttons.a ? 1 : 0;
    payload.bButton = buttons.b ? 1 : 0;
  }

  if (!handEl?.object3D?.visible) return payload;

  const pos = handEl.object3D.position;
  const rot = handEl.object3D.rotation;
  const quat = handEl.object3D.quaternion;

  payload.position = { x: pos.x, y: pos.y, z: pos.z };
  payload.rotation = {
    x: THREE.MathUtils.radToDeg(rot.x),
    y: THREE.MathUtils.radToDeg(rot.y),
    z: THREE.MathUtils.radToDeg(rot.z)
  };
  payload.quaternion = { x: quat.x, y: quat.y, z: quat.z, w: quat.w };
  return payload;
}

AFRAME.registerComponent('telegrip-vr-bridge', {
  init: function () {
    this.leftHand = document.getElementById('leftHand');
    this.rightHand = document.getElementById('rightHand');
    this.leftButtons = { grip: false, trigger: false, x: false, y: false, thumbstick: { x: 0, y: 0, pressed: 0 } };
    this.rightButtons = { grip: false, trigger: false, a: false, b: false, thumbstick: { x: 0, y: 0, pressed: 0 } };

    this.el.renderer.xr.addEventListener('sessionstart', () => {
      state.xrSession = this.el.renderer.xr.getSession();
      attachRigToCamera();
      createBrandHud();
      createTextHud();
    });
    this.el.renderer.xr.addEventListener('sessionend', () => {
      state.xrSession = null;
    });

    this.bindControllerEvents(this.leftHand, 'left', this.leftButtons);
    this.bindControllerEvents(this.rightHand, 'right', this.rightButtons);

    if (state.config?.vr?.controller_axes?.enabled !== false) {
      addControllerAxes(this.leftHand);
      addControllerAxes(this.rightHand);
    }
  },

  sendButtonEvent: function (hand, button, pressed) {
    if (!state.websocket || state.websocket.readyState !== WebSocket.OPEN) return;
    state.websocket.send(JSON.stringify({
      type: pressed ? 'button_press' : 'button_release',
      hand,
      button,
      pressed,
      timestamp: Date.now()
    }));
  },

  sendReleaseEvent: function (hand, releaseKey) {
    if (!state.websocket || state.websocket.readyState !== WebSocket.OPEN) return;
    state.websocket.send(JSON.stringify({
      hand,
      [releaseKey]: true
    }));
  },

  bindControllerEvents: function (handEl, hand, buttons) {
    if (!handEl) return;
    handEl.addEventListener('gripdown', () => { buttons.grip = true; });
    handEl.addEventListener('gripup', () => {
      buttons.grip = false;
      this.sendReleaseEvent(hand, 'gripReleased');
    });
    handEl.addEventListener('triggerdown', () => { buttons.trigger = true; });
    handEl.addEventListener('triggerup', () => {
      buttons.trigger = false;
      this.sendReleaseEvent(hand, 'triggerReleased');
    });

    if (hand === 'left') {
      handEl.addEventListener('xbuttondown', () => {
        buttons.x = true;
        this.sendButtonEvent('left', 'X', true);
      });
      handEl.addEventListener('xbuttonup', () => {
        buttons.x = false;
        this.sendButtonEvent('left', 'X', false);
      });
      handEl.addEventListener('ybuttondown', () => {
        buttons.y = true;
        this.sendButtonEvent('left', 'Y', true);
      });
      handEl.addEventListener('ybuttonup', () => {
        buttons.y = false;
        this.sendButtonEvent('left', 'Y', false);
      });
    } else {
      handEl.addEventListener('abuttondown', () => {
        buttons.a = true;
        this.sendButtonEvent('right', 'A', true);
      });
      handEl.addEventListener('abuttonup', () => {
        buttons.a = false;
        this.sendButtonEvent('right', 'A', false);
      });
      handEl.addEventListener('bbuttondown', () => {
        buttons.b = true;
        this.sendButtonEvent('right', 'B', true);
      });
      handEl.addEventListener('bbuttonup', () => {
        buttons.b = false;
        this.sendButtonEvent('right', 'B', false);
      });
    }
  },

  updateThumbsticks: function () {
    if (!state.xrSession) return;
    const deadzone = 0.05;

    for (const source of state.xrSession.inputSources) {
      if (!source.gamepad || !source.handedness) continue;
      const axes = source.gamepad.axes || [];
      const buttons = source.gamepad.buttons || [];
      const x = Math.abs(axes[2] || 0) < deadzone ? 0 : axes[2] || 0;
      const y = Math.abs(axes[3] || 0) < deadzone ? 0 : axes[3] || 0;
      if (source.handedness === 'left') {
        this.leftButtons.thumbstick = { x, y, pressed: buttons[2]?.pressed ? 1 : 0 };
      }
      if (source.handedness === 'right') {
        this.rightButtons.thumbstick = { x, y, pressed: buttons[3]?.pressed ? 1 : 0 };
      }
    }
  },

  headData: function () {
    const headObject = this.el.camera?.el?.object3D;
    if (!headObject) return { position: null, rotation: null, quaternion: null };

    const pos = headObject.position;
    const rot = headObject.rotation;
    const quat = headObject.quaternion;
    const head = {
      position: { x: pos.x, y: pos.y, z: pos.z },
      rotation: {
        x: THREE.MathUtils.radToDeg(rot.x),
        y: THREE.MathUtils.radToDeg(rot.y),
        z: THREE.MathUtils.radToDeg(rot.z)
      },
      quaternion: { x: quat.x, y: quat.y, z: quat.z, w: quat.w }
    };

    if (state.headText) {
      state.headText.setAttribute(
        'value',
        `Head Pos: ${head.position.x.toFixed(2)} ${head.position.y.toFixed(2)} ${head.position.z.toFixed(2)}\n` +
        `Head Rot: ${head.rotation.x.toFixed(0)} ${head.rotation.y.toFixed(0)} ${head.rotation.z.toFixed(0)}`
      );
    }
    return head;
  },

  tick: function () {
    if (!state.xrSession || !state.websocket || state.websocket.readyState !== WebSocket.OPEN) return;

    this.updateThumbsticks();
    state.websocket.send(JSON.stringify({
      timestamp: Date.now(),
      head: this.headData(),
      leftController: controllerData(this.leftHand, 'left', this.leftButtons),
      rightController: controllerData(this.rightHand, 'right', this.rightButtons)
    }));
  }
});

async function enterVr() {
  const scene = document.querySelector('a-scene');
  if (!scene) return;

  const button = document.getElementById('startVrButton');
  if (button) {
    button.disabled = true;
    button.textContent = 'Starting...';
  }

  try {
    await scene.enterVR(true);
  } catch (error) {
    console.error('Failed to enter VR:', error);
    setStatus(`Failed to enter VR: ${error.message}`);
    if (button) {
      button.disabled = false;
      button.textContent = 'Start VR';
    }
  }
}

async function init() {
  setServerUrl();
  setStatus('Loading configuration...');
  await loadConfig();

  const scene = document.querySelector('a-scene');
  if (scene.hasLoaded) {
    scene.setAttribute('telegrip-vr-bridge', '');
  } else {
    scene.addEventListener('loaded', () => scene.setAttribute('telegrip-vr-bridge', ''), { once: true });
  }

  connectWebSocket();
  attachRigToCamera();
  createBrandHud();
  await setupOptionalCameraPanels();

  const startButton = document.getElementById('startVrButton');
  if (startButton) startButton.addEventListener('click', enterVr);

  scene.addEventListener('enter-vr', () => {
    const launchPanel = document.getElementById('launchPanel');
    if (launchPanel) launchPanel.style.display = 'none';
  });
  scene.addEventListener('exit-vr', () => {
    const launchPanel = document.getElementById('launchPanel');
    const startButton = document.getElementById('startVrButton');
    if (launchPanel) launchPanel.style.display = 'flex';
    if (startButton) {
      startButton.disabled = false;
      startButton.textContent = 'Start VR';
    }
  });
}

document.addEventListener('DOMContentLoaded', () => {
  init().catch(error => {
    console.error('Telegrip startup failed:', error);
    setStatus(`Startup failed: ${error.message}`);
  });
});
