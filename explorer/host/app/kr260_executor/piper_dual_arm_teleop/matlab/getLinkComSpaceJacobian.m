function link_com_jacobian = getLinkComSpaceJacobian(robot, link_transform, link_com_transform)
    link_com_jacobian = zeros(6, robot.num_dof, robot.num_link);
    for i=1:robot.num_link
        col = 1;
        for j=1:i
            if(robot.joint_type(j) == JointType.REVOLUTE)
                link_com_jacobian(1:3,col,i) = cross(link_transform(1:3,1:3,j)*robot.joint_axis(1:3,j), (link_com_transform(1:3,4,i)-link_transform(1:3,4,j)));
                link_com_jacobian(4:6,col,i) = link_transform(1:3,1:3,j)*robot.joint_axis(1:3,j);
                col = col + 1;
            elseif(robot.joint_type(j) == JointType.PRISMATIC)
                link_com_jacobian(1:3,col,i) = link_transform(1:3,1:3,j)*robot.joint_axis(1:3,j);
                link_com_jacobian(4:6,col,i) = zeros(3,1);
                col = col + 1;
            % elseif(robot.joint_type(j) == JointType.FIXED)
            %     link_com_jacobian(1:3,j,i) = zeros(3,1);
            %     link_com_jacobian(4:6,j,i) = zeros(3,1);
            end
        end
    end
end