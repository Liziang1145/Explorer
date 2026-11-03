function centrifugal_coriolis = getCentrifugalCoriolisMatrix(robot, link_com_transform, link_com_jacobian, link_com_jacobian_dot, joint_vel)

    centrifugal_coriolis = zeros(robot.num_dof,robot.num_dof);

    for i=1:robot.num_link

        rotation = link_com_transform(1:3,1:3,i);
        inertia_g = rotation*robot.link_inertia(1:3,1:3,i)*rotation';
 
        % Calculate centrifugal and coriolis force matrix 
        centrifugal_coriolis = centrifugal_coriolis + ...
            link_com_jacobian(1:3,1:robot.num_dof,i)' * robot.link_mass(i) * link_com_jacobian_dot(1:3,1:robot.num_dof,i) + ...
            link_com_jacobian(4:6,1:robot.num_dof,i)' * inertia_g * link_com_jacobian_dot(4:6,1:robot.num_dof,i) + ...
            link_com_jacobian(4:6,1:robot.num_dof,i)' * skew_symmetric(link_com_jacobian(4:6,1:robot.num_dof,i)*joint_vel(1:robot.num_dof,1)) * inertia_g * link_com_jacobian(4:6,1:robot.num_dof,i);
    end

end

function y=skew_symmetric(x)
    y = [0,-x(3),x(2);x(3),0,-x(1);-x(2),x(1),0];
end