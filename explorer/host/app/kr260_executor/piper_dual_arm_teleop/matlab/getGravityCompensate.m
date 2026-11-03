function gravity_force = getGravityCompensate(robot, link_com_jacobian)
    gravity_force = zeros(robot.num_dof,1);
    for i=1:robot.num_link
        % Calculate gravity term
        gravity_force = gravity_force + link_com_jacobian(1:3,1:robot.num_dof,i)' * (robot.link_mass(i)*[0;0;9.81]);
    end
end
