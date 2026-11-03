if (~exist("rbt","var"))
    rbt = importrobot("piper_description.urdf", DataFormat="column");
end
rbt.Gravity(1,1:3) = robot.base_transform(1:3,1:3)' * [0;0;-9.81];
clc;

joint_pos = -0.5 + rand(6,1);
joint_vel = -0.5 + rand(6,1);
joint_acc = -0.5 + rand(6,1);

joint_pos = [joint_pos;0];
joint_vel = [joint_vel;0];
joint_acc = [joint_acc;0];

[link_transform, link_com_transform] = getTransforms(robot, joint_pos);
% [link_lin_vel, link_ang_vel, link_com_lin_vel, link_com_ang_vel] = getLinkVelocity(robot, link_transform, link_com_transform, joint_vel);
% 1-3 line of custom jacobian is J_v, 4-6 line of matlab jacobian is J_w
link_com_jacobian = getLinkSpaceJacobian(robot, link_transform);

% 1-3 line of matlab jacobian is J_w, 4-6 line of matlab jacobian is J_v
jacobian_matlab = zeros(6,6,6);
jacobian_matlab(1:6,1:6,1) = geometricJacobian(rbt,joint_pos(1:6),"link1");
jacobian_matlab(1:6,1:6,2) = geometricJacobian(rbt,joint_pos(1:6),"link2");
jacobian_matlab(1:6,1:6,3) = geometricJacobian(rbt,joint_pos(1:6),"link3");
jacobian_matlab(1:6,1:6,4) = geometricJacobian(rbt,joint_pos(1:6),"link4");
jacobian_matlab(1:6,1:6,5) = geometricJacobian(rbt,joint_pos(1:6),"link5");
jacobian_matlab(1:6,1:6,6) = geometricJacobian(rbt,joint_pos(1:6),"link6");
jacobian_matlab(1:6,1:6,7) = geometricJacobian(rbt,joint_pos(1:6),"gripper_base");

for i=1:7
    jacobian_matlab(1:6,1:6,i) = [jacobian_matlab(4:6,1:6,i);jacobian_matlab(1:3,1:6,i)];
end

disp("custom jacobian");
disp(link_com_jacobian(1:6,1:6,7));

disp("matlab jacobian");
disp(jacobian_matlab(1:6,1:6,7));