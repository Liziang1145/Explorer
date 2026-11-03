function xi = se3_log(T)
    R = T(1:3, 1:3);
    t = T(1:3, 4);

    trR = trace(R);
    cos_theta = (trR - 1) / 2;
    cos_theta = max(min(cos_theta, 1.0), -1.0);  % 防止 acos 输入非法
    theta = acos(cos_theta);

    if abs(theta) < 1e-6
        phi = [R(3,2)-R(2,3); R(1,3)-R(3,1); R(2,1)-R(1,2)] / 2;
        rho = t;
    else
        phi = [R(3,2)-R(2,3); R(1,3)-R(3,1); R(2,1)-R(1,2)];
        phi = phi * theta / (2*sin(theta));

        A = (sin(theta)/theta);
        B = (1 - cos(theta))/(theta^2);
        V_inv = eye(3) - 0.5 * skew(phi) + (1 - (A)/(2*B)) * skew(phi)^2;
        rho = V_inv * t;
    end

    xi = [phi; rho];
end

function S = skew(v)
    S = [0 -v(3) v(2);
         v(3) 0 -v(1);
        -v(2) v(1) 0];
end