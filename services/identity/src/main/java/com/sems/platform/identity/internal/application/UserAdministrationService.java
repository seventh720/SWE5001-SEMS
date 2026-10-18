package com.sems.platform.identity.internal.application;

import com.sems.platform.identity.Role;
import com.sems.platform.identity.UserView;
import com.sems.platform.identity.internal.domain.UserAccount;
import com.sems.platform.identity.internal.persistence.UserAccountRepository;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class UserAdministrationService {

    private final UserAccountRepository users;
    private final org.springframework.jdbc.core.JdbcTemplate jdbc;

    public UserAdministrationService(UserAccountRepository users, org.springframework.jdbc.core.JdbcTemplate jdbc) {
        this.users = users;
        this.jdbc = jdbc;
    }

    public record UserPage(List<UserView> items,int page,int size,long totalElements,int totalPages) {}
    @Transactional(readOnly = true)
    public UserPage listUsers(int page,int size,String search) {
        if(page<0||page>100000||size<1||size>50||search.length()>200)
            throw new org.springframework.web.server.ResponseStatusException(org.springframework.http.HttpStatus.BAD_REQUEST,"Invalid user search or pagination");
        var result=users.search(search.strip(),org.springframework.data.domain.PageRequest.of(page,size,Sort.by("createdAt","id")));
        return new UserPage(result.getContent().stream().map(UserAccount::toView).toList(),page,size,result.getTotalElements(),result.getTotalPages());
    }

    @Transactional
    public UserView replaceRoles(UUID userId, Set<Role> roles) {
        jdbc.query("SELECT pg_advisory_xact_lock(hashtextextended('platform-admin-roles',0))",
                (org.springframework.jdbc.core.RowCallbackHandler) row -> {});
        UserAccount user = users.findById(userId)
                .orElseThrow(() -> new UserNotFoundException(userId));
        if (user.isActive() && user.getRoles().contains(Role.ADMIN) && !roles.contains(Role.ADMIN)
                && jdbc.queryForObject("SELECT count(*) FROM users u JOIN user_roles r ON r.user_id=u.id WHERE u.status='ACTIVE' AND r.role_code='ADMIN'", Long.class) <= 1) {
            throw new org.springframework.web.server.ResponseStatusException(
                    org.springframework.http.HttpStatus.CONFLICT, "At least one active platform administrator must remain");
        }
        user.replaceRoles(roles);
        return user.toView();
    }
}
