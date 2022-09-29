# import pydantic
# import ipaddress

# class NetNodeAddress(pydantic.BaseModel):
# 	mac_address :pydantic.constr(to_lower=True, min_length=17, max_length=17)
# 	ipv4_address :ipaddress.IPv4Address

# 	class Config:
# 		arbitrary_types_allowed = True

# class NetNode(pydantic.BaseModel):
# 	interface: pydantic.constr(to_lower=True, min_length=1, max_length=17)
# 	source: NetNodeAddress
# 	destination: NetNodeAddress
# 	udp_port: int

# 	class Config:
# 		arbitrary_types_allowed = True

