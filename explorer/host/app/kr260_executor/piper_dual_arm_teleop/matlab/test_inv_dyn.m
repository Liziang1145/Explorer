if (~exist("robot", "var"))
    load_robot();
end
if (~exist("rbt","var"))
    rbt = importrobot("piper_description.urdf", DataFormat="column");
end
% rbt.Gravity(1,1:3) = robot.base_transform(1:3,1:3)' * [0;0;-9.81];
rbt.Gravity(1,1:3) = [0,0,-9.81];
clc;

joint_pos = zeros(robot.num_link,1);
joint_vel = zeros(robot.num_link,1);
joint_acc = zeros(robot.num_link,1);

joint_pos(1:robot.num_dof,1) = [0.2;0.2;-0.2;0.2;0.2;0.2];
joint_vel(1:robot.num_dof,1) = [0.2;0.2;-0.2;0.2;0.2;0.2];
joint_acc(1:robot.num_dof,1) = [0.2;0.2;-0.2;0.2;0.2;0.2];

[link_transform, link_com_transform] = getTransforms(robot, joint_pos);
[link_lin_vel, link_ang_vel, link_com_lin_vel, link_com_ang_vel] = getLinkVelocity(robot, link_transform, link_com_transform, joint_vel);
link_com_jacobian = getLinkComSpaceJacobian(robot, link_transform, link_com_transform);
link_com_jacobian_dot = getLinkComSpaceJacobianD(robot, link_transform, link_com_transform, link_lin_vel, link_ang_vel, link_com_lin_vel);
generalized_mass_matrix = getJointSpaceMassMatrix(robot,link_com_transform,link_com_jacobian);
centrifugal_coriolis = getCentrifugalCoriolisMatrix(robot,link_com_transform,link_com_jacobian,link_com_jacobian_dot,joint_vel);
gravity_compensate = getGravityCompensate(robot,link_com_jacobian);
torque = generalized_mass_matrix*joint_acc(1:robot.num_dof,1) + centrifugal_coriolis*joint_vel(1:robot.num_dof,1) + gravity_compensate;

torque_matlab = inverseDynamics(rbt, joint_pos(1:robot.num_dof,1), joint_vel(1:robot.num_dof,1), joint_acc(1:robot.num_dof,1));

disp("custom torque");
disp(torque(1:robot.num_dof,1));

disp("matlab torque");
disp(torque_matlab(1:robot.num_dof,1));


%% Iterative Tests
for i=1:100
    fprintf("%d/100: ",i);
    joint_pos(1:robot.num_dof,1) = robot.joint_limit(1:robot.num_dof,1) + (robot.joint_limit(1:robot.num_dof,2) - robot.joint_limit(1:robot.num_dof,1)).*rand(robot.num_dof,1);
    joint_vel(1:robot.num_dof,1) = -0.5 + rand(robot.num_dof,1);
    joint_acc(1:robot.num_dof,1) = -0.5 + rand(robot.num_dof,1);
    
    [link_transform, link_com_transform] = getTransforms(robot, joint_pos);
    [link_lin_vel, link_ang_vel, link_com_lin_vel, link_com_ang_vel] = getLinkVelocity(robot, link_transform, link_com_transform, joint_vel);
    link_com_jacobian = getLinkComSpaceJacobian(robot, link_transform, link_com_transform);
    link_com_jacobian_dot = getLinkComSpaceJacobianD(robot, link_transform, link_com_transform, link_lin_vel, link_ang_vel, link_com_lin_vel);
    generalized_mass_matrix = getJointSpaceMassMatrix(robot,link_com_transform,link_com_jacobian);
    centrifugal_coriolis = getCentrifugalCoriolisMatrix(robot,link_com_transform,link_com_jacobian,link_com_jacobian_dot,joint_vel);
    gravity_compensate = getGravityCompensate(robot,link_com_jacobian);
    torque = generalized_mass_matrix*joint_acc(1:robot.num_dof,1) + centrifugal_coriolis*joint_vel(1:robot.num_dof,1) + gravity_compensate;
    
    torque_matlab = inverseDynamics(rbt, joint_pos(1:robot.num_dof,1), joint_vel(1:robot.num_dof,1), joint_acc(1:robot.num_dof,1));
    
    if (norm(torque_matlab(1:robot.num_dof,1) - torque(1:robot.num_dof,1)) > 1e-4)
        fprintf("fail.\n");
        disp("joint pos");
        disp(joint_pos(1:robot.num_dof,1));

        disp("joint vel");
        disp(joint_vel(1:robot.num_dof,1));

        disp("joint acc");
        disp(joint_acc(1:robot.num_dof,1));

        disp("custom torque");
        disp(torque(1:robot.num_dof,1));

        disp("matlab torque");
        disp(torque_matlab(1:robot.num_dof,1));
    else
        fprintf("succeed.\n");
    end
end