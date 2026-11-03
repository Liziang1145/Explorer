if (~exist("rbt","var"))
    rbt = importrobot("piper_description.urdf", DataFormat="column");
end
clc;

joint_pos = zeros(robot.num_link,1);
joint_vel = zeros(robot.num_link,1);
joint_acc = zeros(robot.num_link,1);

joint_pos(1:robot.num_dof,1) = robot.joint_limit(1:robot.num_dof,1) + (robot.joint_limit(1:robot.num_dof,2) - robot.joint_limit(1:robot.num_dof,1)).*rand(robot.num_dof,1);
joint_vel(1:robot.num_dof,1) = -0.5 + rand(robot.num_dof,1);
joint_acc(1:robot.num_dof,1) = -0.5 + rand(robot.num_dof,1);
    
[link_transform, link_com_transform] = getTransforms(robot, joint_pos);

transform_matlab = zeros(4,4,robot.num_link);
transform_matlab(1:4,1:4,1) = getTransform(rbt,joint_pos(1:robot.num_dof),"link1");
transform_matlab(1:4,1:4,2) = getTransform(rbt,joint_pos(1:robot.num_dof),"link2");
transform_matlab(1:4,1:4,3) = getTransform(rbt,joint_pos(1:robot.num_dof),"link3");
transform_matlab(1:4,1:4,4) = getTransform(rbt,joint_pos(1:robot.num_dof),"link4");
transform_matlab(1:4,1:4,5) = getTransform(rbt,joint_pos(1:robot.num_dof),"link5");
transform_matlab(1:4,1:4,6) = getTransform(rbt,joint_pos(1:robot.num_dof),"link6");
transform_matlab(1:4,1:4,7) = getTransform(rbt,joint_pos(1:robot.num_dof),"gripper_base");
% transform_matlab(1:4,1:4,8) = getTransform(rbt,joint_pos(1:robot.num_dof),"link7");
% transform_matlab(1:4,1:4,9) = getTransform(rbt,joint_pos(1:robot.num_dof),"link8");

disp("custom transform");
disp(link_transform);

disp("matlab transform");
disp(transform_matlab);