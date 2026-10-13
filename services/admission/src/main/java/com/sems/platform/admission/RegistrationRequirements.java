package com.sems.platform.admission;
public record RegistrationRequirements(boolean realName, boolean email, boolean phone, boolean studentId,
        boolean passport, @jakarta.validation.constraints.Size(max=100) String customFieldLabel) {
    public RegistrationRequirements { customFieldLabel=customFieldLabel==null || customFieldLabel.isBlank()?null:customFieldLabel.strip(); }
    public static RegistrationRequirements none() {return new RegistrationRequirements(false,false,false,false,false,null);}
}
