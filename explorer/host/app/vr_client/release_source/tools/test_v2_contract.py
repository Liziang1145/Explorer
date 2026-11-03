from pathlib import Path
import subprocess
root=Path(__file__).resolve().parents[1]
java=Path(r'C:\Program Files\Android\Android Studio\jbr\bin')
out=root/'vr/build/v2-contract-tests'
out.mkdir(parents=True,exist_ok=True)
source=root/'vr/src/main/java/com/tanluzhe/controlterminal/vr/v2'
names=['Cbor','Packet','ClockSync','ControlGate','SceneStore','Math3','Dashboard','RobotScene','VideoTiming','LossWindow','RttHistory','VrUiState','InputControls','FaceButtons','InputMode','ControllerGeometry','OperatorState','ObservationRate','OperatorCompact','Telemetry','SpeedDisplay','ArmGeometry','LiveSessionState','CaptureConfig','NalUnits','LiveViewBus','CameraLayout','StickButtons','SceneCacheInfo']
subprocess.run([str(java/'javac.exe'),'-encoding','UTF-8','-d',str(out),*[str(source/(n+'.java')) for n in names],str(root/'tests/java/V2ContractTest.java'),str(root/'tests/java/V2Fixture.java')],check=True)
subprocess.run([str(java/'java.exe'),'-cp',str(out),'V2ContractTest'],check=True)
vectors=subprocess.check_output([str(java/'java.exe'),'-cp',str(out),'V2Fixture'],text=True)
(root/'vr/build/v2-contract-vectors.json').write_text(vectors,encoding='utf-8')
