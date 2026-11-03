# piper dual arm teleoperation

This is a dual robotic arm plan & control stack.

## hardware

Dual AgileX Piper 6-axis manipulator.

## feature

* dual arm end effector controlled by VR remote controllers.
* inverse kinematics approximation.
* abnormal motion behaviour filter.
* joint PD control with inverse dynamics feedforward torque.
* mujoco simulation and real hardware control.

## description

`can0` is for left arm;`can1` is for right arm.

## debug

Use script/plot_arm_pos_cmd.py to parse the joint positions commands to dual arms.

## todo

- [ ] Refactor arm model as rigid body tree.
- [ ] Create a config file to replace some constants like ArmModel::num_dof_ and ArmPlanner::num_plan_waypoint_.
- [x] Remove linear and quintic polynomial interpolation methods in `TrajectoryBuffer`.
- [ ] Replace `JointState` in `TrajectoryBuffer::TrajectoryPoint` with `Eigen::Vector<double, ArmModel::num_dof_> joint_pos`
- [ ] Penalize deviation from previous joint position in damped least square inverse kinematics. Cost function: $ cost = \|J^# e\|^2 + \lambda \|q - q_{prev}\|^2 $.
- [ ] Try gradient-based optimizer to solve for inverse kinematics.
- [ ] Program terminated when simulator window is closed by user.
- [ ] Separate inverse kinematics from arm_model.cpp to single header file.