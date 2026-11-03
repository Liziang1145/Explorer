function ad = se3_adjoint(T)
    R = T(1:3, 1:3);
    p = T(1:3, 4);

    ad = [R, zeros(3); skew(p)*R, R];
end

function S = skew(v)
    S = [0 -v(3) v(2);
         v(3) 0 -v(1);
        -v(2) v(1) 0];
end