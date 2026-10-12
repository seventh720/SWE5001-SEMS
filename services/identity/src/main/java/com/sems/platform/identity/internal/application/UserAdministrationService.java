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

    public UserAdministrationService(UserAccountRepository users) {
        this.users = users;
    }

    @Transactional(readOnly = true)
    public List<UserView> listUsers() {
        return users.findAll(Sort.by(Sort.Direction.ASC, "createdAt")).stream()
                .map(UserAccount::toView)
                .toList();
    }

    @Transactional
    public UserView replaceRoles(UUID userId, Set<Role> roles) {
        UserAccount user = users.findById(userId)
                .orElseThrow(() -> new UserNotFoundException(userId));
        user.replaceRoles(roles);
        return user.toView();
    }
}
