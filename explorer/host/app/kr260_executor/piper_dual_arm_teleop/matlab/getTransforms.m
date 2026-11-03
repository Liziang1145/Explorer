function [link_transform, link_com_transform] = getTransforms(robot, joint_pos)

    link_transform = zeros(4,4,robot.num_link);
    link_com_transform = zeros(4,4,robot.num_link);

    for i=1:robot.num_link
        joint_transform_l = eye(4);
        if(robot.joint_type(i) == JointType.REVOLUTE) % revolute joint
            % `rotz()` needs degree
            joint_transform_l(1:3,1:3) = axang2rotm([robot.joint_axis(1:3,i)',joint_pos(i)]);
        elseif(robot.joint_type(i) == JointType.PRISMATIC)
            joint_transform_l(1:3,4) = joint_pos(i)*robot.joint_axis(1:3,i);
        end
        % link transformation in local frame.
        link_transform_l = robot.link_default_transform(1:4,1:4,i) * joint_transform_l;
        if(i == 1)
            link_transform(1:4,1:4,i) = robot.base_transform * link_transform_l;
        else
            link_transform(1:4,1:4,i) = link_transform(1:4,1:4,i-1) * link_transform_l;
        end
        link_com_transform(1:4,1:4,i) = link_transform(1:4,1:4,i) * [eye(3),robot.link_com(1:3,i);0,0,0,1];
    end

end