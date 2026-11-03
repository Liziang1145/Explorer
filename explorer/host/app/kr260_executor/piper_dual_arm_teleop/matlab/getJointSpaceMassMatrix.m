function mass_matrix = getJointSpaceMassMatrix(robot, link_com_transform, link_com_jacobian)

    mass_matrix = zeros(robot.num_dof,robot.num_dof);

    for i=1:robot.num_link

        rotation = link_com_transform(1:3,1:3,i);
        inertia_g = rotation*robot.link_inertia(1:3,1:3,i)*rotation';
 
        % Calculate generalized mass matrix
        mass_matrix = mass_matrix + ...
            link_com_jacobian(1:3,:,i)' * robot.link_mass(i) * link_com_jacobian(1:3,:,i) + ...
            link_com_jacobian(4:6,:,i)' * inertia_g * link_com_jacobian(4:6,:,i);
    end
end
