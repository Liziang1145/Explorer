function end_effector_body_jacobian = getEndEffectorBodyJacobian(robot,link_transform)
    end_effector_body_jacobian = zeros(6, robot.num_dof);
    p = zeros(4,1);
    transform = zeros(4);
    for j=1:robot.num_dof
        if(robot.joint_type(j) == JointType.REVOLUTE)
            p(1:4,1) = link_transform(1:4,1:4,robot.num_link)\[link_transform(1:3,4,j);1];
            transform(1:4,1:4) = link_transform(1:4,1:4,robot.num_link)\link_transform(1:4,1:4,j);
            end_effector_body_jacobian(1:3,j) = cross(transform(1:3,1:3)*robot.joint_axis(1:3,j), p(1:3,1));
            end_effector_body_jacobian(4:6,j) = transform(1:3,1:3)*robot.joint_axis(1:3,j);
        elseif(robot.joint_type(j) == JointType.PRISMATIC)
            end_effector_body_jacobian(1:3,j) = transform(1:3,1:3)*robot.joint_axis(1:3,j);
            end_effector_body_jacobian(4:6,j) = zeros(3,1);
        end
    end
end