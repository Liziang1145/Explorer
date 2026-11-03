const char piper_dual_arm_position_full_xml[] =
R"delimiter(
<mujoco model="piper dual arm">
  <compiler angle="radian" />
  <option timestep="0.001"/>
  <statistic center="0.4 0 0.4" extent="1"/>
  <asset>
    <texture type="skybox" builtin="gradient" rgb1="0.3 0.5 0.7" rgb2="0 0 0" width="512" height="3072"/>
    <texture type="2d" name="groundplane" builtin="checker" mark="edge" rgb1="0.2 0.3 0.4" rgb2="0.1 0.2 0.3"
      markrgb="0.8 0.8 0.8" width="300" height="300"/>
    <material name="groundplane" texture="groundplane" texuniform="true" texrepeat="5 5" reflectance="0.2"/>
  </asset>
  <visual>
    <headlight diffuse="0.6 0.6 0.6" ambient="0.1 0.1 0.1" specular="0 0 0"/>
    <rgba haze="0.15 0.25 0.35 1"/>
    <global azimuth="120" elevation="-20"/>
  </visual>
  <worldbody>
    <light pos="0 0 1.5" dir="0 0 -1" directional="true"/>
    <geom name="floor" size="0 0 0.05" type="plane" material="groundplane" pos="0 0 0"/>
    <body name="left_hand_target" pos="0.8 0.2 0.8" quat="1 0 0 0" mocap="true">
      <geom type="box" size=".05 .05 .05" contype="0" conaffinity="0" rgba=".6 .3 .3 .5"/>
      <site type="sphere" size="0.01" rgba="0 0 1 1" group="1"/>
      <site pos="0 0 0.05" size="0.003 0.003 0.05" type="box" name="left_hand_mocap_site1" rgba="0 0 1 1"/>
      <site pos="0 0.05 0" size="0.003 0.05 0.003" type="box" name="left_hand_mocap_site2" rgba="0 1 0 1"/>
      <site pos="0.05 0 0" size="0.05 0.003 0.003" type="box" name="left_hand_mocap_site3" rgba="1 0 0 1"/>
    </body>
    <body name="right_hand_target" pos="0.8 -0.2 0.8" quat="1 0 0 0" mocap="true">
      <geom type="box" size=".05 .05 .05" contype="0" conaffinity="0" rgba=".6 .3 .3 .5"/>
      <site type="sphere" size="0.01" rgba="0 0 1 1" group="1"/>
      <site pos="0 0 0.05" size="0.003 0.003 0.05" type="box" name="right_hand_mocap_site1" rgba="0 0 1 1"/>
      <site pos="0 0.05 0" size="0.003 0.05 0.003" type="box" name="right_hand_mocap_site2" rgba="0 1 0 1"/>
      <site pos="0.05 0 0" size="0.05 0.003 0.003" type="box" name="right_hand_mocap_site3" rgba="1 0 0 1"/>
    </body>
    <body name="left_arm_base" pos="0.23805 0.19675 0.42" quat="1 0 0 0">
      <body name="left_arm_link1" pos="0 0 0.123">
        <inertial pos="0.000121505 0.000104632 -0.00438597" quat="0.682111 0.730899 0.0143111 -0.0175062" mass="0.71" diaginertia="0.000489262 0.000439887 0.000404551"/>
        <joint name="left_arm_joint1" pos="0 0 0" axis="0 0 1" range="-2.618 2.168"/>
        <body name="left_arm_link2" quat="0.0480084 -0.0480134 -0.705476 -0.705474">
          <inertial pos="0.198666 -0.0109269 0.00142122" quat="0.510131 0.475585 0.525075 0.48773" mass="1.17" diaginertia="0.0679032 0.067745 0.00111966"/>
          <joint name="left_arm_joint2" pos="0 0 0" axis="0 0 1" range="0 3.14"/>
          <body name="left_arm_link3" pos="0.28503 0 0" quat="0.623996 0 0 -0.781427">
            <inertial pos="-0.0202738 -0.133915 -0.000458683" quat="0.706282 0.705111 0.0532202 0.0339395" mass="0.5" diaginertia="0.0138227 0.0138032 0.000244685"/>
            <joint name="left_arm_joint3" pos="0 0 0" axis="0 0 1" range="-2.967 0"/>
            <body name="left_arm_link4" pos="-0.021984 -0.25075 0" quat="0.707105 0.707108 0 0">
              <inertial pos="-9.66636e-05 0.000876064 -0.00496881" quat="0.714689 -0.0948484 0.0635223 0.690064" mass="0.38" diaginertia="0.000191586 0.000185052 0.000152863"/>
              <joint name="left_arm_joint4" pos="0 0 0" axis="0 0 1" range="-1.745 1.745"/>
              <body name="left_arm_link5" quat="0.707105 -0.707108 0 0">
                <inertial pos="-4.10554e-05 -0.0566487 -0.00372058" quat="0.709589 0.704614 0.00134613 -0.00132656" mass="0.383" diaginertia="0.00166169 0.00164328 0.000185028"/>
                <joint name="left_arm_joint5" pos="0 0 0" axis="0 0 1" range="-1.22 1.22"/>
                <body name="left_arm_link6" pos="8.8259e-05 -0.091 0" quat="0.707105 0.707108 0 0">
                  <inertial pos="-0.000182344 7.9409e-05 0.0316207" quat="0.999977 6.30204e-05 0.00678001 0.000789387" mass="0.457" diaginertia="0.000938049 0.000723078 0.000395388"/>
                  <joint name="left_arm_joint6" pos="0 0 0" axis="0 0 1" range="-2.0944 2.0944" damping="0.3"/>
                  <body name="left_arm_link7" pos="0 0 0.1358" quat="0.707105 0.707108 0 0">
                    <inertial pos="0.000651232 -0.049193 0.00972259" quat="0.477798 0.572974 -0.518028 0.418398" mass="0.025" diaginertia="7.74531e-05 7.36783e-05 5.0886e-06"/>
                    <joint name="left_arm_joint7" pos="0 0 0" axis="0 0 1" type="slide" range="0 0.035" limited="true" damping="5"/>
                  </body>
                  <body name="left_arm_link8" pos="0 0 0.1358" quat="-2.59734e-06 -2.59735e-06 -0.707108 -0.707105">
                    <inertial pos="0.000651232 -0.049193 0.00972259" quat="0.477798 0.572974 -0.518028 0.418398" mass="0.025" diaginertia="7.74531e-05 7.36783e-05 5.0886e-06"/>
                    <joint name="left_arm_joint8" pos="0 0 0" axis="0 0 -1" type="slide" range="-0.035 0" limited="true" damping="5"/>
                  </body>
                </body>
              </body>
            </body>
          </body>
        </body>
      </body>
    </body>
    <body name="right_arm_base" pos="0.23805 -0.19675 0.42" quat="1 0 0 0">
      <body name="right_arm_link1" pos="0 0 0.123">
        <inertial pos="0.000121505 0.000104632 -0.00438597" quat="0.682111 0.730899 0.0143111 -0.0175062" mass="0.71" diaginertia="0.000489262 0.000439887 0.000404551"/>
        <joint name="right_arm_joint1" pos="0 0 0" axis="0 0 1" range="-2.618 2.168"/>
        <body name="right_arm_link2" quat="0.0480084 -0.0480134 -0.705476 -0.705474">
          <inertial pos="0.198666 -0.0109269 0.00142122" quat="0.510131 0.475585 0.525075 0.48773" mass="1.17" diaginertia="0.0679032 0.067745 0.00111966"/>
          <joint name="right_arm_joint2" pos="0 0 0" axis="0 0 1" range="0 3.14"/>
          <body name="right_arm_link3" pos="0.28503 0 0" quat="0.623996 0 0 -0.781427">
            <inertial pos="-0.0202738 -0.133915 -0.000458683" quat="0.706282 0.705111 0.0532202 0.0339395" mass="0.5" diaginertia="0.0138227 0.0138032 0.000244685"/>
            <joint name="right_arm_joint3" pos="0 0 0" axis="0 0 1" range="-2.967 0"/>
            <body name="right_arm_link4" pos="-0.021984 -0.25075 0" quat="0.707105 0.707108 0 0">
              <inertial pos="-9.66636e-05 0.000876064 -0.00496881" quat="0.714689 -0.0948484 0.0635223 0.690064" mass="0.38" diaginertia="0.000191586 0.000185052 0.000152863"/>
              <joint name="right_arm_joint4" pos="0 0 0" axis="0 0 1" range="-1.745 1.745"/>
              <body name="right_arm_link5" quat="0.707105 -0.707108 0 0">
                <inertial pos="-4.10554e-05 -0.0566487 -0.00372058" quat="0.709589 0.704614 0.00134613 -0.00132656" mass="0.383" diaginertia="0.00166169 0.00164328 0.000185028"/>
                <joint name="right_arm_joint5" pos="0 0 0" axis="0 0 1" range="-1.22 1.22"/>
                <body name="right_arm_link6" pos="8.8259e-05 -0.091 0" quat="0.707105 0.707108 0 0">
                  <inertial pos="-0.000182344 7.9409e-05 0.0316207" quat="0.999977 6.30204e-05 0.00678001 0.000789387" mass="0.457" diaginertia="0.000938049 0.000723078 0.000395388"/>
                  <joint name="right_arm_joint6" pos="0 0 0" axis="0 0 1" range="-2.0944 2.0944" damping="0.3"/>
                  <body name="right_arm_link7" pos="0 0 0.1358" quat="0.707105 0.707108 0 0">
                    <inertial pos="0.000651232 -0.049193 0.00972259" quat="0.477798 0.572974 -0.518028 0.418398" mass="0.025" diaginertia="7.74531e-05 7.36783e-05 5.0886e-06"/>
                    <joint name="right_arm_joint7" pos="0 0 0" axis="0 0 1" type="slide" range="0 0.035" limited="true" damping="5"/>
                  </body>
                  <body name="right_arm_link8" pos="0 0 0.1358" quat="-2.59734e-06 -2.59735e-06 -0.707108 -0.707105">
                    <inertial pos="0.000651232 -0.049193 0.00972259" quat="0.477798 0.572974 -0.518028 0.418398" mass="0.025" diaginertia="7.74531e-05 7.36783e-05 5.0886e-06"/>
                    <joint name="right_arm_joint8" pos="0 0 0" axis="0 0 -1" type="slide" range="-0.035 0" limited="true" damping="5"/>
                  </body>
                </body>
              </body>
            </body>
          </body>
        </body>
      </body>
    </body>
  </worldbody>
  <actuator>
    <motor name="left_arm_joint1" joint="left_arm_joint1" ctrlrange="-300 300"/>
    <motor name="left_arm_joint2" joint="left_arm_joint2" ctrlrange="-300 300"/>
    <motor name="left_arm_joint3" joint="left_arm_joint3" ctrlrange="-300 300"/>
    <motor name="left_arm_joint4" joint="left_arm_joint4" ctrlrange="-300 300"/>
    <motor name="left_arm_joint5" joint="left_arm_joint5" ctrlrange="-300 300"/>
    <motor name="left_arm_joint6" joint="left_arm_joint6" ctrlrange="-30 30"/>
    <position name="left_arm_joint7" joint="left_arm_joint7" kp="200" user="1" forcelimited="false"/>
    <position name="left_arm_joint8" joint="left_arm_joint8" kp="200" user="1" forcelimited="false"/>
    <motor name="right_arm_joint1" joint="right_arm_joint1" ctrlrange="-300 300"/>
    <motor name="right_arm_joint2" joint="right_arm_joint2" ctrlrange="-300 300"/>
    <motor name="right_arm_joint3" joint="right_arm_joint3" ctrlrange="-300 300"/>
    <motor name="right_arm_joint4" joint="right_arm_joint4" ctrlrange="-300 300"/>
    <motor name="right_arm_joint5" joint="right_arm_joint5" ctrlrange="-300 300"/>
    <motor name="right_arm_joint6" joint="right_arm_joint6" ctrlrange="-60 60"/>
    <position name="right_arm_joint7" joint="right_arm_joint7" kp="200" user="1" forcelimited="false"/>
    <position name="right_arm_joint8" joint="right_arm_joint8" kp="200" user="1" forcelimited="false"/>
  </actuator>
</mujoco>
)delimiter";