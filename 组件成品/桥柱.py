from pyp3d import * 

class 桥柱(Component):

    def __init__(self):
        Component.__init__(self) 
        self['底座长'] = Attr(40000,obvious = True)
        self['底座宽'] = Attr(20000,obvious = True)
        self['底座高'] = Attr(3000,obvious = True)
        self['下底面长'] = Attr(46000,obvious = True)
        self['下底面宽'] = Attr(29500,obvious = True)
        self['中截面长'] = Attr(63800,obvious = True)
        self['中截面宽'] = Attr(42400,obvious = True)
        self['下中距离'] = Attr(48500,obvious = True)
        self['上部柱子底长'] = Attr(13000,obvious = True)
        self['上部柱子底宽'] = Attr(13000,obvious = True)
        self['中上高度'] = Attr(189200,obvious = True)
        self['上部柱子顶长'] = Attr(13000,obvious = True)
        self['上部柱子顶宽'] = Attr(13000,obvious = True)
        self['上部柱子高度'] = Attr(105900,obvious = True)
        self['顶端长'] = Attr(500,obvious = True)
        self['顶端宽'] = Attr(500,obvious = True)
        self['上顶距离'] = Attr(15000,obvious = True)
        self['垫梁宽度'] = Attr(10000,obvious = True)
        self['垫梁高度'] = Attr(8000,obvious = True)
        self['垫石长度']  = Attr(5000,obvious = True)
        self['垫石高度'] = Attr(2412,obvious = True)
        self['桥柱'] = Attr(None,show = True)
        self.replace()

    @export
    def replace(self):
        DL = self['底座长']
        DW = self['底座宽']
        DH = self['底座高']

        XDL = self['下底面长']
        XDW = self['下底面宽']

        ZL = self['中截面长']
        ZW = self['中截面宽']
        XZJ = self['下中距离']
        
        SZDL = self['上部柱子底长']
        SZDW = self['上部柱子底宽']
        ZSJ = self['中上高度']
        
        SZHL = self['上部柱子顶长']
        SZHW = self['上部柱子顶宽']
        SZHH = self['上部柱子高度']
        
        DDL = self['顶端长']
        DDW = self['顶端宽']
        SDJ = self['上顶距离']

        DLW = self['垫梁宽度']
        DLH = self['垫梁高度']
        DSL = self['垫石长度']
        DSH = self['垫石高度']

        ZD1 = ZL/2-XDL/2+ZL/2-XDL/46*20/2
        ZD2 = ZL/2+XDL/46*20/2+ZL/2+XDL/2
        DB = trans(0,0,0)*Section(Vec2(DL/8,0),Vec2(DW-DL/8,0),Vec2(DW,DL/8),Vec2(DW,DL/8*7),Vec2(DW-DL/8,DL),Vec2(DL/8,DL),Vec2(0,DL/8*7),Vec2(0,DL/8),Vec2(DL/8,0))
        DBB = Loft(DB,trans(0,0,DH)*DB)
        D = trans(ZD1/2-DW/2,ZW/2-DL/2,0)*DBB+trans(ZD2/2-DW/2,ZW/2-DL/2,0)*DBB

        Z1 = trans(0,0,XZJ+DH)*Section(Vec2(0,0),Vec2(ZL,0),Vec2(ZL,ZW),Vec2(0,ZW),Vec2(0,0))
        D1 = trans(ZL/2-XDL/2,ZW/2-XDW/2,3000)*Section(Vec2(0,0),Vec2(XDL,0),Vec2(XDL,XDW),Vec2(0,XDW),Vec2(0,0))
        S1 = trans(ZL/2-SZDL/2,ZW/2-SZDW/2,XZJ+DH+ZSJ)*Section(Vec2(0,0),Vec2(SZDL,0),Vec2(SZDL,SZDW),Vec2(0,SZDW),Vec2(0,0))
        S2 = trans(ZL/2-SZHL/2,ZW/2-SZHW/2,XZJ+DH+ZSJ+SZHH)*Section(Vec2(0,0),Vec2(SZHL,0),Vec2(SZHL,SZHW),Vec2(0,SZHW),Vec2(0,0))
        H1 = trans(ZL/2-DDL/2,ZW/2-DDW/2,XZJ+DH+ZSJ+SZHH+SDJ)*Section(Vec2(0,0),Vec2(DDL,0),Vec2(DDL,DDW),Vec2(0,DDW),Vec2(0,0))
        ZT = Loft(D1,Z1)+Loft(Z1,S1)+Loft(S1,S2)+Loft(S2,H1)

        R1 = SZDL/13*6/2
        QPQ = Section(Vec2(ZL/2-XDL/46*20/2,DH),Vec2(ZL/2+XDL/46*20/2,DH),
                      Vec2(ZL/2+ZL/638*408/2,DH+XZJ),
                      Vec2(ZL/2+R1,DH+XZJ+ZSJ/1892*1700),
                      Arc(Vec2(ZL/2+R1,DH+XZJ+ZSJ/1890*1700),
                          Vec2(ZL/2,DH+XZJ+ZSJ/1890*1700+R1),
                          Vec2(ZL/2-R1,DH+XZJ+ZSJ/1890*1700)),
                      Vec2(ZL/2-R1,DH+XZJ+ZSJ/1890*1700),
                      Vec2(ZL/2-ZL/638*408/2,DH+XZJ),
                      Vec2(ZL/2-XDL/46*20/2,DH)) 
        QPQL = rotate(Vec3(1, 0, 0), pi/2) * QPQ
        QP = Loft(QPQL,trans(0,ZW,0) * QPQL)
        R2 = SZDW/13*2
        QPA = Section(Vec2(ZW/2-XDW/295*35/2,DH),
                      Vec2(ZW/2+XDW/295*35/2,DH),
                      Vec2(ZW/2+ZW/424*164/2,DH+XZJ),
                      Vec2(ZW/2+R2,DH+XZJ+ZSJ/1890*1700),
                      Arc(Vec2(ZW/2+R2,DH+XZJ+ZSJ/1890*1700),
                          Vec2(ZW/2,DH+XZJ+ZSJ/1890*1700+R2),
                          Vec2(ZW/2-R2,DH+XZJ+ZSJ/1890*1700)),
                      Vec2(ZW/2-R2,DH+XZJ+ZSJ/1890*1700),
                      Vec2(ZW/2-ZW/424*164/2,DH+XZJ),
                      Vec2(ZW/2-XDW/295*35/2,DH))
        QPWX1 = rotate(Vec3(1,0,0) , pi/2) * QPA 
        QPWX2 = rotate(Vec3(0,0,1) , pi/2) * QPWX1
        QPW = Loft(QPWX2,trans(ZL,0,0) * QPWX2)

        A = ZW/2-ZW/424*164/2
        LTDL1 = scale(ZL/638*408,DLW,DLH)*Cube()
        LTDL = trans(ZL/2-ZL/638*408/2,A/2-DLW/2,DH+XZJ-DLH/2)*LTDL1 + trans(ZL/2-ZL/638*408/2,ZW-A/2-DLW/2,DH+XZJ-DLH/2)*LTDL1
        B = ZL/2-ZL/638*408/2
        LTDW1 = scale(DLW,ZW/424*164,DLH)*Cube()
        LTDW = trans(B/2-DLW/2,A,DH+XZJ-DLH/2)*LTDW1 + trans(ZL-B/2-DLW/2,A,DH+XZJ-DLH/2)*LTDW1
        DS1 = scale(DSL,DLW,DSH)*Cube()
        DS = trans(ZL/2-ZL/638*408/2,A/2-DLW/2,DH+XZJ+DLH/2)*DS1 + trans(ZL/2-ZL/638*408/2,ZW-A/2-DLW/2,DH+XZJ+DLH/2)*DS1 + trans(ZL/2+ZL/638*408/2-DSL,A/2-DLW/2,DH+XZJ+DLH/2)*DS1 + trans(ZL/2+ZL/638*408/2-DSL,ZW-A/2-DLW/2,DH+XZJ+DLH/2)*DS1
        ALL_DLDS = LTDL + LTDW + DS
        self['桥柱'] =  ZT + D - QP - QPW + ALL_DLDS

if __name__ == "__main__":
    FinalGeometry = 桥柱()
    FinalGeometry.replace()
    place(FinalGeometry)






