if (~exist("rbt","var"))
    rbt = importrobot("piper_description.urdf", DataFormat="column");
end
rbt.Gravity(1,1:3) = [0,0,-9.81];
clc;

joint_pos = zeros(robot.num_link,1);
joint_pos(1:robot.num_dof,1) = robot.joint_limit(1:robot.num_dof,1) + (robot.joint_limit(1:robot.num_dof,2) - robot.joint_limit(1:robot.num_dof,1)).*rand(robot.num_dof,1);

[link_transform, link_com_transform] = getTransforms(robot, joint_pos);
link_com_jacobian = getLinkComSpaceJacobian(robot, link_transform, link_com_transform);

gravity_torque = getGravityCompensate(robot,link_com_jacobian);
gravity_torque_matlab = gravityTorque(rbt, joint_pos(1:robot.num_dof));

disp("custom gravity torque")
disp(gravity_torque(1:robot.num_dof));

disp("matlab gravity torque");
disp(gravity_torque_matlab);