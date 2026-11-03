function [link_lin_vel, link_ang_vel, link_com_lin_vel, link_com_ang_vel] = getLinkVelocity(robot, link_transform, link_com_transform, joint_vel)
    link_lin_vel = zeros(3, robot.num_link);
    link_ang_vel = zeros(3, robot.num_link);
    link_com_lin_vel = zeros(3, robot.num_link);
    for i=1:robot.num_link
        rotation = link_transform(1:3,1:3,i);
        if (i==1)
            link_translation = link_transform(1:3,4,i);
            com_translation = link_com_transform(1:3,4,i);
        else
            link_translation = link_transform(1:3,4,i) - link_transform(1:3,4,i-1);
            com_translation = link_com_transform(1:3,4,i) - link_transform(1:3,4,i);
        end
        if(robot.joint_type(i) == JointType.REVOLUTE)
            if(i == 1)
                link_ang_vel(1:3,i) = rotation * robot.joint_axis(1:3,i) * joint_vel(i);
                link_lin_vel(1:3,i) = cross(link_ang_vel(1:3,i), link_translation);
                link_com_lin_vel(1:3,i) = cross(link_ang_vel(1:3,i), com_translation);
            else
                link_ang_vel(1:3,i) = link_ang_vel(1:3,i-1) + rotation * robot.joint_axis(1:3,i) * joint_vel(i);
                link_lin_vel(1:3,i) = link_lin_vel(1:3,i-1) + cross(link_ang_vel(1:3,i-1), link_translation);
                link_com_lin_vel(1:3,i) = link_lin_vel(1:3,i) + cross(link_ang_vel(1:3,i), com_translation);
            end
        elseif(robot.joint_type(i) == JointType.PRISMATIC)
            if(i == 1)
                link_ang_vel(1:3,i) = zeros(3,1);
                link_lin_vel(1:3,i) = cross(link_ang_vel(1:3,i),link_translation) + rotation * robot.joint_axis(1:3,i) * joint_vel(i);
            else
                link_ang_vel(1:3,i) = link_ang_vel(1:3,i-1);
                link_lin_vel(1:3,i) = link_lin_vel(1:3,i-1) + cross(link_ang_vel(1:3,i),link_translation) + rotation * robot.joint_axis(1:3,i) * joint_vel(i);
            end
        elseif(robot.joint_type(i) == JointType.FIXED)
            if(i == 1)
                link_ang_vel(1:3,i) = zeros(3,1);
                link_lin_vel(1:3,i) = zeros(3,1);
                link_com_lin_vel(1:3,i) = zeros(3,1);
            else
                link_ang_vel(1:3,i) = link_ang_vel(1:3,i-1);
                link_lin_vel(1:3,i) = link_lin_vel(1:3,i-1) + cross(link_ang_vel(1:3,i-1),link_translation);
                link_com_lin_vel(1:3,i) = link_lin_vel(1:3,i) + cross(link_ang_vel(1:3,i), com_translation);
            end
        end
    end
    link_com_ang_vel = link_ang_vel;
    end